"""Named workflows compiled into plans (Phase 6, engine in Phase 15).

A workflow is a plan somebody wrote down and reviewed, instead of one a model
produced at request time. For the recurring work in a plant - an inspection
analysis, a shift report, a maintenance investigation - that is the right
trade: the sequence is known, and "the same request produced a different
sequence today" is not an acceptable property.

So this module compiles a registered workflow definition into the same
:class:`~backend.orchestrator.src.plan.Plan` the planner produces. Downstream,
nothing can tell the difference: the execution manager, the approval gates and
the verifier all behave identically. That is the point - a workflow is not a
second execution path, it is a pre-written plan.

Validation happens at compile time, not at run time:

* every ``tool`` step must name a registered tool;
* ``depends_on`` may only reference earlier steps (``Plan`` rejects cycles);
* ``{{inputs.x}}`` placeholders must be satisfied by the caller's inputs, and
  an unresolved placeholder is an error rather than the literal string
  ``{{inputs.x}}`` being passed to a tool.

Approval requirements declared in a workflow can only *add* gates. A workflow
cannot mark a step as pre-approved; that decision belongs to the approval
policy and the reviewer, not to a YAML file.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.orchestrator.src.plan import MAX_STEPS, Plan, PlanStep

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\{\{\s*inputs\.([A-Za-z0-9_]+)\s*\}\}")


class WorkflowError(ValueError):
    reason = "workflow_invalid"


class WorkflowNotFound(KeyError):
    reason = "workflow_not_found"

    def __init__(self, name: str, available: list[str] | None = None) -> None:
        detail = f"workflow '{name}' is not registered"
        if available:
            detail += f"; available: {', '.join(sorted(available))}"
        super().__init__(detail)
        self.name = name

    def __str__(self) -> str:  # KeyError repr quotes the message otherwise
        return self.args[0] if self.args else "workflow not found"


class WorkflowManager:
    def __init__(self, registry: Any, *, tool_names: list[str] | None = None) -> None:
        self._registry = registry
        self._tool_names = set(tool_names or [])

    def set_tool_names(self, names: list[str]) -> None:
        """Called once at startup, after the tool registry is populated."""
        self._tool_names = set(names or [])

    def list(self) -> list[dict[str, Any]]:
        definitions = []
        for definition in self._registry.list():
            definitions.append(
                {
                    "name": definition.name,
                    "description": getattr(definition, "description", ""),
                    "version": getattr(definition, "version", "1"),
                    "steps": len(getattr(definition, "steps", []) or []),
                    "inputs": list(getattr(definition, "inputs", []) or []),
                }
            )
        return definitions

    def compile(
        self,
        name: str,
        *,
        inputs: dict[str, Any] | None = None,
        task: str | None = None,
    ) -> Plan:
        try:
            definition = self._registry.get(name)
        except KeyError as exc:
            raise WorkflowNotFound(name, [d.name for d in self._registry.list()]) from exc

        raw_steps = list(getattr(definition, "steps", []) or [])
        if not raw_steps:
            raise WorkflowError(
                f"workflow '{name}' has no steps; a workflow with no steps would "
                "report success without doing anything"
            )
        if len(raw_steps) > MAX_STEPS:
            raise WorkflowError(
                f"workflow '{name}' declares {len(raw_steps)} steps, over the "
                f"{MAX_STEPS} step limit"
            )

        supplied = dict(inputs or {})
        required = list(getattr(definition, "inputs", []) or [])
        missing = [key for key in required if key not in supplied]
        if missing:
            raise WorkflowError(
                f"workflow '{name}' requires input(s) {', '.join(missing)}"
            )

        steps: list[PlanStep] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_steps):
            step = self._compile_step(raw, index=index, workflow=name, inputs=supplied, seen=seen)
            steps.append(step)
            seen.add(step.id)

        if not any(step.kind == "verify" for step in steps):
            steps.append(
                PlanStep(
                    id="verify",
                    kind="verify",
                    name="verifier",
                    description="Check evidence, citations, calculations and artifacts",
                    depends_on=[steps[-1].id],
                    timeout_seconds=180,
                )
            )

        return Plan(
            goal=task or f"workflow: {name}",
            steps=steps,
            origin="workflow",
            agent=getattr(definition, "agent", None),
            notes=f"workflow '{name}' v{getattr(definition, 'version', '1')}",
        )

    def _compile_step(
        self,
        raw: Any,
        *,
        index: int,
        workflow: str,
        inputs: dict[str, Any],
        seen: set[str],
    ) -> PlanStep:
        data = raw if isinstance(raw, dict) else getattr(raw, "__dict__", {})
        kind = str(data.get("kind", "")).strip().lower()
        if kind not in {"retrieve", "agent", "tool", "verify"}:
            raise WorkflowError(
                f"workflow '{workflow}' step {index + 1} has unsupported kind '{kind}'"
            )

        step_id = str(data.get("id") or f"step{index + 1}")
        if step_id in seen:
            raise WorkflowError(f"workflow '{workflow}' reuses step id '{step_id}'")

        step_name = str(data.get("name") or "").strip() or None
        if kind == "tool":
            if not step_name:
                raise WorkflowError(
                    f"workflow '{workflow}' step '{step_id}' is a tool step with no tool name"
                )
            if self._tool_names and step_name not in self._tool_names:
                raise WorkflowError(
                    f"workflow '{workflow}' step '{step_id}' names unregistered tool "
                    f"'{step_name}'"
                )

        depends = [str(dep) for dep in (data.get("depends_on") or [])]
        unknown = [dep for dep in depends if dep not in seen]
        if unknown:
            raise WorkflowError(
                f"workflow '{workflow}' step '{step_id}' depends on unknown step(s) "
                f"{', '.join(unknown)}"
            )

        arguments = self._resolve(data.get("arguments") or {}, inputs=inputs, workflow=workflow)

        return PlanStep(
            id=step_id,
            kind=kind,  # type: ignore[arg-type]
            name=step_name,
            description=str(data.get("description", ""))[:500],
            arguments=arguments,
            depends_on=depends,
            timeout_seconds=float(data.get("timeout_seconds") or 180),
            # A workflow may demand approval; it may never waive it.
            requires_approval=bool(data.get("requires_approval", False)),
        )

    def _resolve(self, value: Any, *, inputs: dict[str, Any], workflow: str) -> Any:
        """Substitute ``{{inputs.key}}`` placeholders, erroring on unknown keys."""
        if isinstance(value, str):
            match = _PLACEHOLDER.fullmatch(value.strip())
            if match:
                key = match.group(1)
                if key not in inputs:
                    raise WorkflowError(
                        f"workflow '{workflow}' references undefined input '{key}'"
                    )
                return inputs[key]

            def replace(found: re.Match[str]) -> str:
                key = found.group(1)
                if key not in inputs:
                    raise WorkflowError(
                        f"workflow '{workflow}' references undefined input '{key}'"
                    )
                return str(inputs[key])

            return _PLACEHOLDER.sub(replace, value)
        if isinstance(value, dict):
            return {
                key: self._resolve(item, inputs=inputs, workflow=workflow)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._resolve(item, inputs=inputs, workflow=workflow) for item in value]
        return value
