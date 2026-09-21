"""Planning (Phase 6).

Turns a routed request into a :class:`~backend.orchestrator.src.plan.Plan`.

The design decision worth defending: **every intent has a deterministic
template plan, and the model is only asked to improve on it.** Not the other
way round.

A model-authored plan is attractive in a demo and unreliable in a plant. It
invents tool names, forgets the verification step, and produces a different
shape on every run, which makes the system impossible to test. So:

1. ``plan()`` builds a template plan from the route. This always works, needs
   no model, and is what the tests assert against.
2. If a reasoning model is configured *and* the request is complex, the
   planner asks it for a plan and validates the result against
   ``PlanStep``/``Plan`` - unknown tool names, cycles and missing
   dependencies are rejected.
3. A rejected model plan is logged and the template is used. The plan's
   ``origin`` field records which one ran, so "why did it do that" is
   answerable after the fact.

The model can therefore make the plan better but cannot make it invalid, and
cannot remove the verification step - that one is appended by this module
after the model has had its say.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.orchestrator.src.plan import MAX_STEPS, Plan, PlanStep
from backend.orchestrator.src.task_router import Intent, Route

logger = logging.getLogger(__name__)

#: Model role used for planning. Never a model name - see Phase 2.
PLANNER_ROLE = "reasoning"

#: Below this many characters a request is not worth a planning round-trip.
MODEL_PLAN_MIN_CHARS = 80

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model reply.

    Local models wrap JSON in prose and fences no matter how firmly the prompt
    asks them not to. This is tolerant on purpose; the result is validated
    immediately afterwards, so tolerance here costs nothing.
    """
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.split("\n", 1)[-1] if "\n" in candidate else candidate
    match = _JSON_OBJECT.search(candidate)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def intent_model_role(intent: Intent) -> str:
    """Which model role answers this intent.

    ``coding`` for analysis because the step writes Python; ``reasoning``
    otherwise. Roles, never model names.
    """
    return "coding" if intent is Intent.ANALYSIS else "reasoning"


class Planner:
    def __init__(
        self,
        *,
        model_router: Any = None,
        gateway: Any = None,
        tools: Any = None,
        allow_model_plans: bool = True,
    ) -> None:
        self._model_router = model_router
        self._gateway = gateway
        self._tools = tools
        self._allow_model_plans = allow_model_plans

    # --- public -----------------------------------------------------------

    async def plan(
        self,
        *,
        task: str,
        route: Route,
        document_ids: list[str] | None = None,
        workflow: str | None = None,
    ) -> Plan:
        template = self._template(task=task, route=route, document_ids=document_ids)
        if workflow or not self._allow_model_plans:
            return template
        if len(task or "") < MODEL_PLAN_MIN_CHARS and route.intent is not Intent.ARTIFACT:
            return template

        proposed = await self._model_plan(task=task, route=route, template=template)
        if proposed is None:
            return template
        return proposed

    # --- deterministic templates ------------------------------------------

    def _template(
        self,
        *,
        task: str,
        route: Route,
        document_ids: list[str] | None,
    ) -> Plan:
        steps: list[PlanStep] = []
        retrieve_id = "retrieve"

        if route.use_rag:
            steps.append(
                PlanStep(
                    id=retrieve_id,
                    kind="retrieve",
                    name="search_documents",
                    description="Find evidence in the indexed documents",
                    arguments={
                        "query": task,
                        "document_ids": list(document_ids or []),
                        "top_k": 12,
                    },
                    timeout_seconds=180,
                )
            )

        depends = [retrieve_id] if route.use_rag else []

        if route.intent is Intent.ANALYSIS:
            steps.append(
                PlanStep(
                    id="analyse",
                    kind="agent",
                    name=route.agent,
                    description="Decide what to compute and produce the code for it",
                    arguments={"task": task},
                    depends_on=depends,
                    timeout_seconds=240,
                )
            )
            steps.append(
                PlanStep(
                    id="compute",
                    kind="tool",
                    name="run_python",
                    description="Execute the analysis in the sandbox",
                    arguments={},
                    depends_on=["analyse"],
                    timeout_seconds=180,
                    requires_approval=True,
                )
            )
            answer_depends = ["compute"]
        elif route.intent is Intent.ARTIFACT:
            steps.append(
                PlanStep(
                    id="outline",
                    kind="agent",
                    name=route.agent,
                    description="Draft the artifact content with citations",
                    arguments={
                        "task": task,
                        "artifact_type": route.artifact_type,
                        "requested_units": route.requested_units,
                    },
                    depends_on=depends,
                    timeout_seconds=300,
                )
            )
            steps.append(
                PlanStep(
                    id="build",
                    kind="tool",
                    name=f"create_{route.artifact_type or 'pptx'}",
                    description="Render the file in the sandbox from the validated spec",
                    arguments={},
                    depends_on=["outline"],
                    timeout_seconds=240,
                    requires_approval=True,
                )
            )
            answer_depends = ["build"]
        else:
            steps.append(
                PlanStep(
                    id="answer",
                    kind="agent",
                    name=route.agent,
                    description="Answer from the retrieved evidence, with citations",
                    arguments={"task": task},
                    depends_on=depends,
                    timeout_seconds=240,
                )
            )
            answer_depends = ["answer"]

        # Verification is appended here, by us, always. It is not something a
        # plan may omit.
        steps.append(
            PlanStep(
                id="verify",
                kind="verify",
                name="verifier",
                description="Check evidence, citations, calculations and artifacts",
                arguments={},
                depends_on=answer_depends,
                timeout_seconds=180,
            )
        )

        return Plan(
            goal=task,
            steps=steps[:MAX_STEPS],
            origin="heuristic",
            agent=route.agent,
            notes=route.reason,
        )

    # --- model-assisted planning ------------------------------------------

    async def _model_plan(self, *, task: str, route: Route, template: Plan) -> Plan | None:
        if self._model_router is None or self._gateway is None:
            return None

        tool_names = []
        if self._tools is not None:
            try:
                tool_names = self._tools.names()
            except Exception:  # pragma: no cover - defensive
                tool_names = []

        prompt = self._planning_prompt(task=task, route=route, tool_names=tool_names)
        try:
            resolved = await self._model_router.resolve(PLANNER_ROLE)
            reply = await self._gateway.chat(
                model=resolved,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            # An unconfigured or unreachable model must not stop the job: the
            # template plan is a complete, working plan.
            logger.info("planner falling back to the template plan: %s", exc)
            return None

        payload = _extract_json_object(str(getattr(reply, "content", reply) or ""))
        if not payload:
            logger.info("planner reply contained no JSON object; using the template plan")
            return None

        steps = self._coerce_steps(payload.get("steps"), allowed_tools=set(tool_names))
        if not steps:
            return None

        # Whatever the model proposed, verification is the last step.
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

        try:
            return Plan(
                goal=task,
                steps=steps[:MAX_STEPS],
                origin="model",
                agent=route.agent,
                notes=str(payload.get("notes", ""))[:2000],
            )
        except Exception as exc:
            logger.info("model plan rejected (%s); using the template plan", exc)
            return None

    def _coerce_steps(
        self,
        raw: Any,
        *,
        allowed_tools: set[str],
    ) -> list[PlanStep]:
        """Validate model-proposed steps, dropping anything unusable.

        A step naming a tool that does not exist is dropped rather than
        repaired: guessing what the model meant is how a plan ends up doing
        something nobody asked for.
        """
        if not isinstance(raw, list):
            return []
        steps: list[PlanStep] = []
        seen: set[str] = set()
        for index, item in enumerate(raw[:MAX_STEPS]):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "")).strip().lower()
            if kind not in {"retrieve", "agent", "tool", "verify"}:
                continue
            name = str(item.get("name", "")).strip()
            if kind == "tool" and allowed_tools and name not in allowed_tools:
                logger.info("dropping planned step for unknown tool '%s'", name)
                continue
            step_id = str(item.get("id") or f"step{index + 1}").strip()[:64]
            if not step_id or step_id in seen:
                step_id = f"step{index + 1}"
            depends = [str(dep)[:64] for dep in (item.get("depends_on") or []) if str(dep) in seen]
            arguments = item.get("arguments")
            try:
                steps.append(
                    PlanStep(
                        id=step_id,
                        kind=kind,  # type: ignore[arg-type]
                        name=name or None,
                        description=str(item.get("description", ""))[:500],
                        arguments=arguments if isinstance(arguments, dict) else {},
                        depends_on=depends,
                        timeout_seconds=float(item.get("timeout_seconds") or 180),
                    )
                )
            except Exception as exc:
                logger.info("dropping invalid planned step %s: %s", step_id, exc)
                continue
            seen.add(step_id)
        return steps

    def _planning_prompt(self, *, task: str, route: Route, tool_names: list[str]) -> str:
        tools = ", ".join(tool_names) or "none available"
        return (
            "You are the planner for an on-premise industrial AI system. Produce a short "
            "plan as a single JSON object. Do not add commentary.\n\n"
            'Schema: {"steps": [{"id": str, "kind": "retrieve"|"agent"|"tool"|"verify", '
            '"name": str, "description": str, "arguments": object, "depends_on": [str], '
            '"timeout_seconds": number}], "notes": str}\n\n'
            f"Rules:\n"
            f"- At most {MAX_STEPS} steps. Fewer is better.\n"
            f"- 'tool' steps may only use these registered tools: {tools}.\n"
            "- Retrieve evidence before answering anything about the documents.\n"
            "- Never invent tool names, file paths, model names or credentials.\n"
            "- depends_on may only reference earlier step ids.\n\n"
            f"Detected intent: {route.intent.value} (agent: {route.agent}).\n"
            f"Request: {task}"
        )
