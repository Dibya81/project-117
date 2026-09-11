"""Plans and plan steps (Phase 6).

A plan is the contract between the planner (which may be a language model)
and the execution manager (which must never trust one). Everything a step can
ask for is bounded here, so an over-enthusiastic or manipulated plan fails
validation instead of becoming behaviour:

- at most :data:`MAX_STEPS` steps, so no unbounded agent loops;
- a per-step timeout capped at :data:`MAX_STEP_TIMEOUT_SECONDS`;
- ``kind`` restricted to four verbs the executor actually implements;
- ``depends_on`` validated as a DAG, so a cyclic plan cannot deadlock the
  worker;
- ``name`` checked against the live tool/agent registries by the planner
  before a ``Plan`` is ever constructed.

Note what a step *cannot* express: a container image, a shell command outside
a tool, a model name, or a permission. Those are policy, and policy does not
come from a plan.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Hard ceiling on plan length. Twelve is generous for the workflows in
#: docs/workflows and small enough that a runaway plan is obvious.
MAX_STEPS = 12

#: No single step may hold a worker longer than this (15 minutes).
MAX_STEP_TIMEOUT_SECONDS = 900.0

#: The four things the execution manager knows how to do.
StepKind = Literal["retrieve", "agent", "tool", "verify"]

StepStatus = Literal["ok", "error", "skipped", "awaiting_approval"]


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    kind: StepKind
    #: Tool name, agent name, or a label for retrieve/verify steps.
    name: str = Field(default="", max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, max_length=MAX_STEPS)
    timeout_seconds: float = Field(default=120.0, gt=0, le=MAX_STEP_TIMEOUT_SECONDS)
    #: Set by a workflow author for a step that must always be gated. Tool risk
    #: also gates independently at the registry, so this only adds friction,
    #: never removes it.
    requires_approval: bool = False
    description: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _name_required_for_dispatch(self) -> PlanStep:
        if self.kind in ("tool", "agent") and not self.name.strip():
            raise ValueError(f"a '{self.kind}' step must name the {self.kind} to run")
        if self.id in self.depends_on:
            raise ValueError(f"step '{self.id}' depends on itself")
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=2000)
    steps: list[PlanStep] = Field(min_length=1, max_length=MAX_STEPS)
    #: "model" | "heuristic" | "workflow" - recorded so a demo failure can be
    #: attributed to planning rather than execution.
    origin: str = Field(default="heuristic", max_length=32)
    agent: str | None = Field(default=None, max_length=64)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _validate_graph(self) -> Plan:
        ids = [step.id for step in self.steps]
        duplicates = {value for value in ids if ids.count(value) > 1}
        if duplicates:
            raise ValueError(f"duplicate step id(s): {', '.join(sorted(duplicates))}")
        known = set(ids)
        for step in self.steps:
            unknown = [dep for dep in step.depends_on if dep not in known]
            if unknown:
                raise ValueError(
                    f"step '{step.id}' depends on unknown step(s): {', '.join(unknown)}"
                )
        # Cycle detection: layering must consume every step.
        remaining = {step.id: set(step.depends_on) for step in self.steps}
        while remaining:
            ready = [sid for sid, deps in remaining.items() if not deps]
            if not ready:
                stuck = ", ".join(sorted(remaining))
                raise ValueError(f"plan contains a dependency cycle among: {stuck}")
            for sid in ready:
                remaining.pop(sid)
            for deps in remaining.values():
                deps.difference_update(ready)
        return self

    def step(self, step_id: str) -> PlanStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def tool_names(self) -> list[str]:
        return sorted({step.name for step in self.steps if step.kind == "tool"})

    def agent_names(self) -> list[str]:
        return sorted({step.name for step in self.steps if step.kind == "agent"})

    def waves(self) -> list[list[PlanStep]]:
        """Group steps into dependency layers.

        Steps inside a wave are independent and are run concurrently; waves run
        in order. Concurrency comes from the declared graph rather than from
        the executor guessing what is safe to parallelise.
        """
        by_id = {step.id: step for step in self.steps}
        pending = {step.id: set(step.depends_on) for step in self.steps}
        done: set[str] = set()
        layers: list[list[PlanStep]] = []
        while pending:
            ready = sorted(sid for sid, deps in pending.items() if deps <= done)
            if not ready:  # pragma: no cover - prevented by _validate_graph
                raise ValueError("plan contains a dependency cycle")
            layers.append([by_id[sid] for sid in ready])
            for sid in ready:
                pending.pop(sid)
            done.update(ready)
        return layers


class StepOutcome(BaseModel):
    """What actually happened for one step. Assembled into the job trace."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    kind: str
    name: str = ""
    status: StepStatus = "ok"
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    attempts: int = 1

    def summary(self) -> dict[str, Any]:
        """Compact form for ``jobs.result_json`` - no retrieved content."""
        return {
            "step_id": self.step_id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1),
            "attempts": self.attempts,
            "error": self.error,
        }
