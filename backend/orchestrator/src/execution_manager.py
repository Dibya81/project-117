"""Step execution (Phase 6).

Walks a validated plan and runs its steps. Four things happen here and nowhere
else:

**Dispatch by kind.** ``retrieve`` builds context, ``agent`` asks a
specialised agent, ``tool`` goes through the registry, ``verify`` is left to
the verification manager. A step cannot invent a fifth kind because ``PlanStep``
rejects it.

**Dependency order.** Steps run in waves derived from ``depends_on``, so a
step never sees a dependency that has not produced its output yet. Steps in
the same wave run concurrently - retrieval against two document sets is
parallel, and there is no reason to make a user wait for it serially.

**Approval, as an interrupt.** When the registry raises
``ToolApprovalRequired``, this manager raises :class:`ApprovalInterrupt`
carrying the step id. Nothing has run at that point: no container, no file, no
connector call. The orchestrator parks the job, and resuming re-enters this
manager with that step id in ``approved_steps``.

**Cancellation, checked between steps.** A cancel request cannot kill a
running container mid-write, so it is honoured at step boundaries -
predictable, and it never leaves a half-written artifact behind.

What this manager refuses to do is continue past a failure. It raises, and the
orchestrator's recovery manager decides between retry, replan, park and fail.
Swallowing a failed step and carrying on is how you end up with a confident
answer built on a step that did not happen.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from backend.orchestrator.src.context_manager import ContextPack
from backend.orchestrator.src.plan import Plan, PlanStep, StepOutcome
from backend.tools.base import ToolApprovalRequired, ToolContext

logger = logging.getLogger(__name__)


class JobCancelled(RuntimeError):
    reason = "job_cancelled"

    def __init__(self, job_id: str) -> None:
        super().__init__(f"job '{job_id}' was cancelled")
        self.job_id = job_id


class ApprovalInterrupt(RuntimeError):
    """A step needs human approval. Raised *before* the step does anything."""

    reason = "approval_required"

    def __init__(
        self,
        message: str,
        *,
        step_id: str,
        tool: str | None = None,
        risk: str | None = None,
    ) -> None:
        super().__init__(message)
        self.step_id = step_id
        self.tool = tool
        self.risk = risk

    def as_request(self) -> dict[str, Any]:
        """Payload stored on the job and shown to the reviewer."""
        return {
            "step_id": self.step_id,
            "tool": self.tool,
            "risk": self.risk,
            "reason": str(self),
        }


@dataclass
class ExecutionState:
    """Everything accumulated while a plan runs.

    Persisted between an approval park and its resume, which is why it is a
    plain data object rather than a closure over local variables.
    """

    job_id: str
    task: str
    plan: Plan
    user: str | None = None
    roles: tuple[str, ...] = ()
    document_ids: list[str] = field(default_factory=list)
    #: Step ids a reviewer has approved.
    approved_steps: set[str] = field(default_factory=set)
    outcomes: dict[str, StepOutcome] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    context: ContextPack | None = None
    answer: str = ""
    agent: str | None = None
    model: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    sandbox_execution_ids: list[str] = field(default_factory=list)
    #: Per-job data constraints (document scope, chunk cap, redaction).
    #: Enforced in ``_do_retrieve``. ``None`` means the caller supplied none,
    #: which is the unscoped default - not a bypass of anything.
    data_policy: Any = None
    #: Deployment tool constraints (allow/deny, risk ceiling, call budget).
    #: Enforced in ``_do_tool`` on every call, not once at plan time, because
    #: a replan can introduce a step the original check never saw.
    tool_policy: Any = None
    #: Tool invocations made so far in this job, checked against the budget.
    tool_calls: int = 0
    #: Policy outcomes recorded so the UI can explain a refusal.
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)

    def completed(self, step_id: str) -> bool:
        outcome = self.outcomes.get(step_id)
        return outcome is not None and outcome.status == "ok"

    def evidence(self) -> list[dict[str, Any]]:
        return self.context.evidence_dicts() if self.context else []

    def trace(self) -> list[dict[str, Any]]:
        """Ordered record of what actually ran. Surfaced in the result."""
        return [
            self.outcomes[step.id].summary()
            for step in self.plan.steps
            if step.id in self.outcomes
        ]


@dataclass(frozen=True)
class _RunHooks:
    """Callbacks for one run. Job-scoped, so two concurrent jobs cannot
    report each other's progress."""

    progress: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None
    is_cancelled: Callable[[str], Awaitable[bool]] | None = None


class ExecutionManager:
    def __init__(
        self,
        *,
        tools: Any,
        agent_manager: Any,
        context_manager: Any,
        progress: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        is_cancelled: Callable[[str], Awaitable[bool]] | None = None,
        session_factory: Any = None,
        audit: Any = None,
        retrieval: Any = None,
        sandbox: Any = None,
        artifacts: Any = None,
        model_router: Any = None,
    ) -> None:
        self._tools = tools
        self._agents = agent_manager
        self._context = context_manager
        self._progress = progress
        self._is_cancelled = is_cancelled
        self._session_factory = session_factory
        self._audit = audit
        self._retrieval = retrieval
        self._sandbox = sandbox
        self._artifacts = artifacts
        self._model_router = model_router

    async def run(
        self,
        state: ExecutionState,
        *,
        progress: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        is_cancelled: Callable[[str], Awaitable[bool]] | None = None,
    ) -> ExecutionState:
        """Run a plan to completion.

        ``progress`` and ``is_cancelled`` may be supplied per run. One manager
        instance serves every job in the process, so a job-scoped callback has
        to arrive with the run rather than be baked into the constructor -
        otherwise progress from two concurrent jobs lands on whichever job the
        constructor happened to know about.
        """
        hooks = _RunHooks(
            progress=progress if progress is not None else self._progress,
            is_cancelled=is_cancelled if is_cancelled is not None else self._is_cancelled,
        )
        for wave in state.plan.waves():
            pending = [
                step
                for step in wave
                if step.kind != "verify" and not state.completed(step.id)
            ]
            if not pending:
                continue

            await self._check_cancelled(hooks, state)

            if len(pending) == 1:
                await self._run_step(pending[0], state, hooks)
                continue

            # Concurrent wave. gather with return_exceptions so one failure
            # does not leave siblings running unobserved; the first exception
            # is then raised deliberately.
            results = await asyncio.gather(
                *(self._run_step(step, state, hooks) for step in pending),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
        return state

    # --- one step ---------------------------------------------------------

    async def _run_step(
        self, step: PlanStep, state: ExecutionState, hooks: "_RunHooks"
    ) -> None:
        state.attempts[step.id] = state.attempts.get(step.id, 0) + 1
        started = time.perf_counter()
        await self._emit(
            hooks,
            state,
            f"{step.kind}: {step.description or step.name or step.id}",
            {
                "step_id": step.id,
                "kind": step.kind,
                "name": step.name,
                "status": "started",
                "job_id": state.job_id,
            },
        )

        try:
            if step.kind == "retrieve":
                output = await self._do_retrieve(step, state)
            elif step.kind == "agent":
                output = await self._do_agent(step, state)
            elif step.kind == "tool":
                output = await self._do_tool(step, state)
            else:  # pragma: no cover - verify is handled by the orchestrator
                output = {"skipped": step.kind}
        except ToolApprovalRequired as exc:
            state.outcomes[step.id] = StepOutcome(
                step_id=step.id,
                kind=step.kind,
                name=step.name,
                status="awaiting_approval",
                duration_ms=(time.perf_counter() - started) * 1000,
                attempts=state.attempts[step.id],
            )
            raise ApprovalInterrupt(
                str(exc),
                step_id=step.id,
                tool=getattr(exc, "tool", step.name),
                risk=getattr(exc, "risk", None),
            ) from exc
        except Exception as exc:
            state.outcomes[step.id] = StepOutcome(
                step_id=step.id,
                kind=step.kind,
                name=step.name,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - started) * 1000,
                attempts=state.attempts[step.id],
            )
            raise

        state.outcomes[step.id] = StepOutcome(
            step_id=step.id,
            kind=step.kind,
            name=step.name,
            status="ok",
            output=output if isinstance(output, dict) else {"value": output},
            duration_ms=(time.perf_counter() - started) * 1000,
            attempts=state.attempts[step.id],
        )
        await self._emit(
            hooks,
            state,
            f"{step.kind} step '{step.name or step.id}' finished",
            {
                "step_id": step.id,
                "kind": step.kind,
                "name": step.name,
                "status": "ok",
                "job_id": state.job_id,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )

    # --- dispatch ---------------------------------------------------------

    async def _do_retrieve(self, step: PlanStep, state: ExecutionState) -> dict[str, Any]:
        arguments = dict(step.arguments or {})
        requested_docs = arguments.get("document_ids") or state.document_ids or None
        top_k = int(arguments.get("top_k") or 12)

        # Data policy. A step cannot widen the document scope the caller
        # granted, and cannot drag more of the corpus into context than the
        # deployment allows. Refused rather than silently trimmed: quietly
        # returning fewer documents produces an answer that looks complete
        # and is not.
        policy = state.data_policy
        if policy is not None:
            scoped = policy.scope_documents(requested_docs)
            requested_docs = scoped or None
            top_k = policy.cap_chunks(top_k)
            state.policy_decisions.append(
                {
                    "stepId": step.id,
                    "policy": "data",
                    "allowed": True,
                    "detail": {"documentCount": len(scoped), "topK": top_k},
                }
            )

        pack = await self._context.build(
            query=str(arguments.get("query") or state.task),
            use_rag=True,
            document_ids=requested_docs,
            top_k=top_k,
            user=state.user,
        )
        state.context = pack
        return pack.summary()

    async def _do_agent(self, step: PlanStep, state: ExecutionState) -> dict[str, Any]:
        arguments = dict(step.arguments or {})
        result = await self._agents.run(
            name=step.name or state.plan.agent or "documentation",
            task=str(arguments.get("task") or state.task),
            context=state.context,
            job_id=state.job_id,
            user=state.user,
            roles=state.roles,
            arguments=arguments,
        )
        answer = str(result.get("answer", "") or "")
        if answer:
            state.answer = answer
        state.agent = result.get("agent") or step.name
        state.model = result.get("model") or state.model
        return result

    async def _do_tool(self, step: PlanStep, state: ExecutionState) -> dict[str, Any]:
        arguments = self._resolve_arguments(step, state)

        # Tool policy, checked per call rather than once at plan time: a
        # replan or a recovery retry can introduce a step the plan-time sweep
        # never saw. The registry still applies RBAC and approval afterwards;
        # this gate is about deployment reach, which the registry does not know.
        state.tool_calls += 1
        policy = state.tool_policy
        if policy is not None:
            policy.check_budget(state.tool_calls)
            spec = self._spec_for(step.name or "")
            if spec is not None:
                decision = policy.check(spec, roles=state.roles or None)
                state.policy_decisions.append(
                    {"stepId": step.id, "policy": "tool", **decision.to_dict()}
                )

        context = ToolContext(
            job_id=state.job_id,
            user=state.user,
            roles=state.roles,
            document_ids=list(state.document_ids),
            retrieval=self._retrieval,
            sandbox=self._sandbox,
            artifacts=self._artifacts,
            session_factory=self._session_factory,
            audit=self._audit,
            router=self._model_router,
        )
        result = await self._tools.execute(
            step.name or "",
            arguments,
            context,
            step_id=step.id,
            approved=step.id in state.approved_steps,
            agent=state.agent,
        )
        if result.sandbox_execution_id:
            state.sandbox_execution_ids.append(result.sandbox_execution_id)
        if result.artifact_ids:
            state.artifact_ids.extend(result.artifact_ids)
        artifact = (result.output or {}).get("artifact")
        if isinstance(artifact, dict):
            state.artifacts.append(artifact)
        return dict(result.output or {})

    def _resolve_arguments(self, step: PlanStep, state: ExecutionState) -> dict[str, Any]:
        """Fill a tool step's arguments from its dependencies' outputs.

        A plan says "run the analysis the agent just designed"; the code the
        agent produced lives in that step's outcome, not in the plan. Only
        known keys are transferred - never a blind dict merge, which would let
        an agent's output overwrite something like a document filter.
        """
        arguments = dict(step.arguments or {})
        degraded: list[str] = []
        for dependency in step.depends_on:
            outcome = state.outcomes.get(dependency)
            if outcome is None or not outcome.output:
                continue
            output = outcome.output
            if output.get("degraded"):
                degraded.append(dependency)
            if "code" in output and "code" not in arguments:
                arguments["code"] = output["code"]
            if "spec" in output and "spec" not in arguments:
                arguments["spec"] = output["spec"]
            if "filename" in output and "filename" not in arguments:
                arguments["filename"] = output["filename"]
        if step.name == "run_python" and "code" not in arguments:
            # The upstream agent marks itself degraded when the model's reply
            # carried no ```python fence, so there is no script to run. Calling
            # the tool anyway produced "ToolArgumentError: code: Field
            # required", which surfaced as the opaque job error "unhandled
            # ToolArgumentError". Say what actually went wrong instead.
            detail = (
                f"step '{degraded[0]}' produced no runnable code block"
                if degraded
                else "no dependency supplied a code block"
            )
            from backend.tools.base import ToolArgumentError

            raise ToolArgumentError(
                f"'{step.name}' has no code to execute: {detail}. The model reply "
                "did not contain a ```python fence, so the sandbox step was skipped "
                "rather than run against empty input."
            )
        if step.name and step.name.startswith("create_") and "spec" not in arguments:
            # A generator with no spec is a bug worth surfacing early rather
            # than an empty file worth debugging later.
            arguments["spec"] = {}
        return arguments

    # --- helpers ----------------------------------------------------------

    def _spec_for(self, name: str) -> Any:
        """The registry's spec for a tool, or ``None`` if it has none.

        A missing spec is not a grant: the registry refuses unknown tools on
        its own, so returning ``None`` here defers to that refusal instead of
        inventing a second, weaker one.
        """
        if not name or self._tools is None:
            return None
        try:
            return next((s for s in self._tools.specs() if s.name == name), None)
        except Exception:  # pragma: no cover - a broken registry is not a grant
            return None

    async def _check_cancelled(self, hooks: "_RunHooks", state: ExecutionState) -> None:
        if hooks.is_cancelled is None:
            return
        if await hooks.is_cancelled(state.job_id):
            raise JobCancelled(state.job_id)

    async def _emit(
        self,
        hooks: "_RunHooks",
        state: ExecutionState,
        message: str,
        detail: dict[str, Any],
    ) -> None:
        if hooks.progress is None:
            return
        try:
            await hooks.progress(message, detail)
        except Exception:  # pragma: no cover - progress is advisory
            logger.debug("progress callback failed for job %s", state.job_id, exc_info=True)
