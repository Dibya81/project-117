"""Orchestrator (Phase 6) - the central brain.

One job, one state machine, one place that decides what happens next:

    QUEUED -> PLANNING -> [RETRIEVING] -> EXECUTING -> VERIFYING -> COMPLETED
                              |              |            |
                              +--------------+------------+--> NEEDS_APPROVAL
                                             |                  FAILED
                                             |                  CANCELLED
                                             +----------------> TIMEOUT

The orchestrator owns the transitions; the managers own the work. It:

- classifies the request (``task_router``),
- gets a validated plan (``planner``),
- applies the four execution policies (``orchestrator.policies``),
- executes it wave by wave (``execution_manager``),
- verifies the output before it is allowed to be a success
  (``verification_manager``),
- and decides what a failure means (``recovery_manager``).

Four properties are deliberate and worth stating:

**Nothing reaches COMPLETED without passing through VERIFYING.** That is
enforced twice - by the transition table in ``jobs.state`` and by this file
only ever calling ``COMPLETED`` from the verification branch.

**Policy is checked before the first step, not at the first violation.**
``ActionPolicy`` refuses a plan the caller may not run as a whole, so a
permission problem can never leave a half-executed plan behind. ``ToolPolicy``
also rejects an over-budget plan up front, and again per call inside the
execution manager, because a replan can introduce a step the first sweep
never saw.

**Approval parks a job before the side effect.** The plan-level approval
policy parks the job before execution starts; ``ApprovalInterrupt`` from the
tool registry remains the second line of defence for anything the plan-level
sweep could not resolve. Either way nothing has run when the job parks: no
container, no file, no connector call.

**A policy refusal is not a retryable failure.** The recovery manager is for
infrastructure faults. Retrying a refusal would just spend the retry budget
arriving at the same answer, so refusals bypass recovery and fail the job
with the reason the reviewer needs to see.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.jobs.state import JobState
from backend.orchestrator.policies import (
    ActionPolicy,
    DataScopeViolation,
    PlanApprovalPolicy,
    ToolPolicy,
    policy_for_job,
)
from backend.orchestrator.src.execution_manager import (
    ApprovalInterrupt,
    ExecutionState,
    JobCancelled,
)
from backend.orchestrator.src.plan import Plan
from backend.orchestrator.src.recovery_manager import RecoveryAction
from backend.security.egress import EgressBlocked, EgressPolicy
from backend.security.rbac import AuthorizationError
from backend.tools.base import ToolPermissionDenied

logger = logging.getLogger(__name__)

#: Keys stored alongside the plan blob that are not part of the Plan model.
_PLAN_EXTRA_KEYS = ("awaiting_step", "pending_steps", "approved_steps", "route")

#: Refusals. These are answers, not faults, so they skip the recovery manager.
_REFUSALS = (
    AuthorizationError,
    ToolPermissionDenied,
    DataScopeViolation,
    EgressBlocked,
)


class Orchestrator:
    def __init__(
        self,
        *,
        jobs: Any,
        planner: Any,
        task_router: Any,
        context_manager: Any,
        execution_manager: Any,
        verification_manager: Any,
        recovery_manager: Any,
        agent_manager: Any,
        tools: Any,
        workflow_manager: Any = None,
        retrieval: Any = None,
        sandbox: Any = None,
        artifacts: Any = None,
        session_factory: Any = None,
        audit: Any = None,
        model_router: Any = None,
        metrics: Any = None,
        action_policy: ActionPolicy | None = None,
        tool_policy: ToolPolicy | None = None,
        approval_policy: PlanApprovalPolicy | None = None,
        egress: EgressPolicy | None = None,
        max_chunks_per_step: int = 24,
        max_verification_retries: int = 1,
    ) -> None:
        self._jobs = jobs
        self._planner = planner
        self._router = task_router
        self._context = context_manager
        self._execution = execution_manager
        self._verification = verification_manager
        self._recovery = recovery_manager
        self._agents = agent_manager
        self._tools = tools
        self._workflows = workflow_manager
        self._retrieval = retrieval
        self._sandbox = sandbox
        self._artifacts = artifacts
        self._session_factory = session_factory
        self._audit = audit
        self._model_router = model_router
        self._metrics = metrics
        # Policies. Defaulted rather than optional-and-skipped: an orchestrator
        # built without an explicit policy still gets the conservative one.
        self._action_policy = action_policy or ActionPolicy(tools=tools)
        self._tool_policy = tool_policy or ToolPolicy()
        self._approval_policy = approval_policy or PlanApprovalPolicy(tools=tools)
        self._egress = egress or EgressPolicy()
        self._max_chunks_per_step = max(1, int(max_chunks_per_step))
        self._max_verification_retries = max_verification_retries
        #: Strong references to background tasks; without these the event loop
        #: may garbage-collect a running job mid-flight.
        self._tasks: set[asyncio.Task[Any]] = set()

    # --- public API -------------------------------------------------------

    async def submit(
        self,
        *,
        task: str,
        kind: str = "chat",
        user: str | None = None,
        roles: list[str] | None = None,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
        use_rag: bool = True,
        workflow: str | None = None,
        inputs: dict[str, Any] | None = None,
        background: bool = True,
    ) -> dict[str, Any]:
        """Accept a task and return the job immediately (HTTP 202 shape)."""
        request = {
            "document_ids": document_ids or [],
            "use_rag": use_rag,
            "workflow": workflow,
            "inputs": inputs or {},
            "roles": roles or [],
        }
        job = await asyncio.to_thread(
            self._jobs.create,
            kind=kind,
            task=task,
            user=user,
            session_id=session_id,
            request=request,
        )
        if background:
            self._spawn(job["id"])
        return job

    async def run(self, job_id: str, *, approved_steps: set[str] | None = None) -> dict[str, Any]:
        """Drive one job to a terminal state. Never raises for job failure."""
        try:
            return await self._run(job_id, approved_steps=approved_steps or set())
        except Exception as exc:  # noqa: BLE001 - a crashed job must still land
            logger.exception("orchestrator crashed on job %s", job_id)
            try:
                return await asyncio.to_thread(
                    self._jobs.fail,
                    job_id,
                    error=f"orchestrator error: {exc.__class__.__name__}: {exc}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("could not mark job %s failed", job_id)
                return {"id": job_id, "state": JobState.FAILED.value}

    async def resume(self, job_id: str) -> dict[str, Any]:
        """Continue a job that a human just approved."""
        job = await asyncio.to_thread(self._jobs.get, job_id)
        self._spawn(job_id)
        return job

    def spawn(self, job_id: str, *, approved_steps: set[str] | None = None) -> None:
        """Start a job in the background.

        ``approved_steps`` is optional because the approved set is also
        recorded on the job. A caller that resumes without it - the approve
        route does exactly that - still gets the steps the reviewer signed
        off, instead of parking again on the same step forever.
        """
        self._spawn(job_id, approved_steps=approved_steps)

    # --- the run ----------------------------------------------------------

    async def _run(self, job_id: str, *, approved_steps: set[str]) -> dict[str, Any]:
        job = await asyncio.to_thread(self._jobs.get, job_id)
        request = job.get("request") or {}
        task = job.get("task") or ""
        stored = job.get("plan") or {}
        resuming = job.get("state") == JobState.EXECUTING.value and bool(stored)

        approved = {str(step) for step in (approved_steps or ())}
        if resuming:
            approved |= self._approved_from_stored(stored)

        roles = [str(role) for role in (request.get("roles") or [])]
        document_ids = [str(doc) for doc in (request.get("document_ids") or [])]

        # 1. plan (or reuse the plan we parked on)
        if resuming:
            plan = _plan_from_stored(stored)
            route_summary = stored.get("route") or {}
        else:
            await self._transition(job_id, JobState.PLANNING, "classifying and planning")
            plan, route_summary = await self._build_plan(job_id, task, request, roles=roles)

        # 2. policy - refuse or park before anything runs
        blocked = await self._apply_policies(
            job_id, plan, roles=roles, approved=approved, route_summary=route_summary
        )
        if blocked is not None:
            return blocked

        # 3. execute
        state = ExecutionState(
            job_id=job_id,
            task=task,
            plan=plan,
            user=job.get("user"),
            roles=tuple(roles),
            document_ids=document_ids,
            approved_steps=approved,
            data_policy=policy_for_job(
                self._egress,
                document_ids=document_ids,
                max_chunks_per_step=self._max_chunks_per_step,
            ),
            tool_policy=self._tool_policy,
        )
        outcome_state = await self._execute(job_id, state, route_summary=route_summary)
        if outcome_state is None:
            # Parked, cancelled, refused or failed inside _execute; it already
            # wrote the terminal (or NEEDS_APPROVAL) state.
            return await asyncio.to_thread(self._jobs.get, job_id)

        # 4. verify, then complete
        return await self._verify_and_finish(job_id, outcome_state, route_summary=route_summary)

    # --- planning ---------------------------------------------------------

    async def _build_plan(
        self,
        job_id: str,
        task: str,
        request: dict[str, Any],
        *,
        roles: list[str] | None = None,
    ) -> tuple[Plan, dict[str, Any]]:
        workflow_name = request.get("workflow")
        if workflow_name and self._workflows is not None:
            # `inputs` is keyword-only on WorkflowManager.compile; passing it
            # positionally raised TypeError, so the workflow branch never ran.
            plan = self._workflows.compile(
                workflow_name, inputs=request.get("inputs") or {}
            )
            route_summary = {"workflow": workflow_name}
        else:
            # TaskRouter exposes exactly one entry point, `await route(...)`,
            # which returns a Route. This call site had been written against a
            # different API — `set_available_agents()` (which never existed) and
            # a synchronous `classify()` — so every non-workflow job died with
            # an AttributeError before planning began.
            #
            # Tool pre-filtering by caller role is no longer applied here: the
            # Planner receives its tool registry at construction, and the
            # previous `tool_names=`/`agent_names=` keywords are not part of its
            # signature. Policy is still enforced at execution time by
            # `_tool_policy.permitted(...)`, so an unpermitted tool is refused
            # with a clear error rather than silently running; the plan simply
            # is not pruned in advance.
            route = await self._router.route(
                task,
                workflow=workflow_name,
                use_rag=request.get("use_rag"),
                document_ids=request.get("document_ids") or None,
            )
            if not request.get("use_rag", True):
                # Route carries `use_rag`; `needs_retrieval` was never a field.
                route.use_rag = False
            plan = await self._planner.plan(
                task=task,
                route=route,
                document_ids=request.get("document_ids") or None,
            )
            route_summary = route.to_dict()
        await asyncio.to_thread(
            self._jobs.set_plan, job_id, {**plan.model_dump(), "route": route_summary}
        )
        await asyncio.to_thread(
            self._jobs.progress,
            job_id,
            message=f"plan ready ({plan.origin}, {len(plan.steps)} steps)",
            detail={
                "origin": plan.origin,
                "steps": [step.name for step in plan.steps],
                "route": route_summary,
            },
        )
        return plan, route_summary

    def _permitted_tool_names(self, roles: list[str] | None) -> list[str]:
        """Tool names the planner may use for this caller.

        Falls back to the registry's full list only if the registry cannot
        produce specs - the policy needs a spec to make a decision, and
        guessing from a name would be a decision made on no evidence.

        NOTE: currently unused. It fed `Planner.plan(tool_names=...)`, a
        parameter that does not exist on the real Planner, which receives its
        tool registry at construction. Kept because it is the correct
        implementation of a capability the design wants - per-caller plan-time
        tool pruning - and deleting it would make restoring that capability a
        rewrite rather than a call. Execution-time enforcement in
        `_apply_policies` is unaffected and remains authoritative.
        """
        try:
            specs = list(self._tools.specs())
        except Exception:  # pragma: no cover - defensive
            return list(self._tools.names())
        permitted = self._tool_policy.permitted(specs, roles=roles or None)
        return [spec.name for spec in permitted]

    # --- policy -----------------------------------------------------------

    async def _apply_policies(
        self,
        job_id: str,
        plan: Plan,
        *,
        roles: list[str],
        approved: set[str],
        route_summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Gate the plan. Returns ``None`` to proceed, else the parked/failed job."""
        # Action policy: does the caller hold every permission this plan needs?
        try:
            decisions = [
                decision.to_dict()
                for decision in self._action_policy.enforce(plan, roles=roles)
            ]
        except AuthorizationError as exc:
            return await self._refuse(job_id, exc, policy="action")

        # Tool policy: is the plan within the deployment's call budget? Each
        # call is checked again at execution time.
        tool_steps = [step for step in plan.steps if step.kind == "tool"]
        try:
            self._tool_policy.check_budget(len(tool_steps))
        except ToolPermissionDenied as exc:
            return await self._refuse(job_id, exc, policy="tool")

        if decisions:
            await asyncio.to_thread(
                self._jobs.progress,
                job_id,
                message=f"policy: {len(decisions)} step(s) permitted",
                detail={"policy": "action", "decisions": decisions},
            )

        # Approval policy: park before the work, not after it.
        gated = self._approval_policy.gated_steps(plan, approved_steps=approved)
        if gated:
            await self._park(
                job_id, plan, gated, approved=approved, route_summary=route_summary
            )
            return await asyncio.to_thread(self._jobs.get, job_id)
        return None

    async def _refuse(self, job_id: str, exc: Exception, *, policy: str) -> dict[str, Any]:
        await asyncio.to_thread(
            self._jobs.fail,
            job_id,
            error=f"refused by {policy} policy: {exc}",
            detail={"policy": policy, "error": f"{type(exc).__name__}: {exc}"},
        )
        self._count("job.policy_refused")
        return await asyncio.to_thread(self._jobs.get, job_id)

    async def _park(
        self,
        job_id: str,
        plan: Plan,
        gated: list[Any],
        *,
        approved: set[str],
        route_summary: dict[str, Any],
    ) -> None:
        """Park the job for review.

        Every gated step is listed in the approval request, and one approval
        covers exactly that list. The reviewer is shown each step, its tool
        and its risk, so approving grants what was displayed - not a blanket
        permission, and not an endless park-approve-park loop through a plan
        with three risky steps.
        """
        pending = [item.step_id for item in gated]
        await asyncio.to_thread(
            self._jobs.set_plan,
            job_id,
            {
                **plan.model_dump(),
                "route": route_summary,
                "awaiting_step": pending[0],
                "pending_steps": pending,
                "approved_steps": sorted(approved),
            },
        )
        first = gated[0]
        await asyncio.to_thread(
            self._jobs.request_approval,
            job_id,
            request={
                "step_id": first.step_id,
                "tool": first.tool,
                "risk": first.risk,
                "reason": first.reason,
                "steps": [item.to_dict() for item in gated],
            },
            message=first.reason or "approval required",
        )
        self._count("job.needs_approval")

    @staticmethod
    def _approved_from_stored(stored: dict[str, Any]) -> set[str]:
        approved = {str(step) for step in (stored.get("approved_steps") or [])}
        approved |= {str(step) for step in (stored.get("pending_steps") or [])}
        awaiting = stored.get("awaiting_step")
        if awaiting:
            approved.add(str(awaiting))
        return approved

    # --- execution --------------------------------------------------------

    async def _execute(
        self,
        job_id: str,
        state: ExecutionState,
        *,
        route_summary: dict[str, Any],
        replans_used: int = 0,
        retries_used: int = 0,
    ) -> ExecutionState | None:
        tracker = _ProgressTracker(self._jobs, job_id)
        try:
            return await self._execution.run(
                state,
                progress=tracker.on_progress,
                is_cancelled=self._is_cancelled,
            )
        except ApprovalInterrupt as interrupt:
            # The registry refused a call the plan-level sweep could not
            # resolve (an unknown tool, or a spec only the registry has).
            await asyncio.to_thread(
                self._jobs.set_plan,
                job_id,
                {
                    **state.plan.model_dump(),
                    "route": route_summary,
                    "awaiting_step": interrupt.step_id,
                    "pending_steps": [interrupt.step_id],
                    "approved_steps": sorted(state.approved_steps),
                },
            )
            await asyncio.to_thread(
                self._jobs.request_approval,
                job_id,
                request=interrupt.as_request(),
                message=str(interrupt),
            )
            self._count("job.needs_approval")
            return None
        except JobCancelled:
            await asyncio.to_thread(self._jobs.cancel, job_id)
            self._count("job.cancelled")
            return None
        except _REFUSALS as exc:
            # Not a fault. Retrying spends the budget to reach the same answer.
            await asyncio.to_thread(
                self._jobs.fail,
                job_id,
                error=f"refused by policy: {exc}",
                detail={
                    "policy": type(exc).__name__,
                    "decisions": state.policy_decisions,
                    "trace": state.trace(),
                },
            )
            self._count("job.policy_refused")
            return None
        except Exception as exc:  # noqa: BLE001 - classified below
            decision = self._recovery.classify(
                exc, attempts=retries_used, replans=replans_used
            )
            await asyncio.to_thread(
                self._jobs.progress,
                job_id,
                message=f"recovery: {decision.action.value}",
                detail={"reason": decision.reason},
            )
            if decision.action is RecoveryAction.RETRY:
                await asyncio.sleep(decision.delay_seconds)
                return await self._execute(
                    job_id,
                    _restart(state),
                    route_summary=route_summary,
                    replans_used=replans_used,
                    retries_used=retries_used + 1,
                )
            if decision.action is RecoveryAction.REPLAN:
                new_plan, new_route = await self._build_plan(
                    job_id,
                    state.task,
                    {"use_rag": True, "roles": list(state.roles)},
                    roles=list(state.roles),
                )
                # A new plan is new work: re-gate it rather than inheriting
                # the first plan's clearance.
                blocked = await self._apply_policies(
                    job_id,
                    new_plan,
                    roles=list(state.roles),
                    approved=set(state.approved_steps),
                    route_summary=new_route,
                )
                if blocked is not None:
                    return None
                return await self._execute(
                    job_id,
                    _restart(state, plan=new_plan),
                    route_summary=new_route,
                    replans_used=replans_used + 1,
                    retries_used=retries_used,
                )
            if decision.action is RecoveryAction.CANCEL:
                await asyncio.to_thread(self._jobs.cancel, job_id)
                self._count("job.cancelled")
                return None
            await asyncio.to_thread(
                self._jobs.fail,
                job_id,
                error=decision.reason,
                detail={"trace": state.trace()},
            )
            self._count("job.failed")
            return None

    # --- verification -----------------------------------------------------

    async def _verify_and_finish(
        self,
        job_id: str,
        state: ExecutionState,
        *,
        route_summary: dict[str, Any],
    ) -> dict[str, Any]:
        failed_steps = [
            outcome for outcome in state.outcomes.values() if outcome.status == "error"
        ]
        if failed_steps and not state.answer:
            reason = "; ".join(f"{o.step_id}: {o.error}" for o in failed_steps)
            await asyncio.to_thread(
                self._jobs.fail, job_id, error=reason, detail={"trace": state.trace()}
            )
            self._count("job.failed")
            return await asyncio.to_thread(self._jobs.get, job_id)

        await self._transition(job_id, JobState.VERIFYING, "checking evidence and artifacts")
        evidence = state.evidence()
        report = await self._verification.verify(
            task=state.task,
            answer=state.answer,
            evidence=evidence,
            artifacts=state.artifacts,
            job_id=job_id,
            user=state.user,
        )
        allowed, reason = self._verification.may_complete(report)
        result = {
            "answer": state.answer,
            "evidence": evidence,
            "artifacts": state.artifacts,
            "artifact_ids": state.artifact_ids,
            "sandbox_execution_ids": state.sandbox_execution_ids,
            "agent": state.agent,
            "model": state.model,
            "grounded": bool(state.context.has_evidence) if state.context else False,
            "route": route_summary,
            "plan_origin": state.plan.origin,
            "context": state.context.summary() if state.context else {},
            "policy": state.policy_decisions,
            "trace": state.trace(),
        }
        await asyncio.to_thread(
            self._jobs.set_result, job_id, result=result, verification=report.summary()
        )
        if not allowed:
            await asyncio.to_thread(
                self._jobs.fail,
                job_id,
                error=reason or "verification failed",
                detail=report.summary(),
            )
            self._count("job.verification_failed")
            return await asyncio.to_thread(self._jobs.get, job_id)

        await self._transition(
            job_id,
            JobState.COMPLETED,
            "verified",
            detail={"verification": report.summary()},
        )
        self._count("job.completed")
        return await asyncio.to_thread(self._jobs.get, job_id)

    # --- helpers ----------------------------------------------------------

    def _spawn(self, job_id: str, *, approved_steps: set[str] | None = None) -> None:
        task = asyncio.create_task(self.run(job_id, approved_steps=approved_steps))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _is_cancelled(self, job_id: str) -> bool:
        """Checked between steps. A cancel cannot kill a running container
        mid-write, so it is honoured at a boundary where nothing is half-done.
        """
        try:
            job = await asyncio.to_thread(self._jobs.get, job_id)
        except Exception:  # pragma: no cover - a lookup failure is not a cancel
            return False
        return str(job.get("state")) in {
            JobState.CANCELLED.value,
            JobState.TIMEOUT.value,
        }

    async def _transition(
        self,
        job_id: str,
        target: JobState,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._jobs.transition, job_id, target, message=message, detail=detail
        )

    def _count(self, key: str) -> None:
        if self._metrics is not None:
            self._metrics.incr(key)


class _ProgressTracker:
    """Moves the job between RETRIEVING and EXECUTING as steps actually run.

    The alternative - declaring the state up front from the plan shape - lies
    whenever a plan re-queries after computing. Following the steps means the
    state column always describes what the job is doing right now.
    """

    _STATE_FOR_KIND = {
        "retrieve": JobState.RETRIEVING,
        "agent": JobState.EXECUTING,
        "tool": JobState.EXECUTING,
    }

    def __init__(self, jobs: Any, job_id: str) -> None:
        self._jobs = jobs
        self._job_id = job_id
        self._current: JobState | None = None

    async def on_progress(self, message: str, detail: dict[str, Any]) -> None:
        if detail.get("status") == "started":
            target = self._STATE_FOR_KIND.get(str(detail.get("kind")))
            if target is not None and target is not self._current:
                await asyncio.to_thread(
                    self._jobs.transition,
                    self._job_id,
                    target,
                    message=message,
                    detail=detail,
                )
                self._current = target
                return
        await asyncio.to_thread(
            self._jobs.progress, self._job_id, message=message, detail=detail
        )


def _restart(state: ExecutionState, *, plan: Plan | None = None) -> ExecutionState:
    """A fresh state for a retry or replan.

    Outcomes and attempt counts are deliberately dropped: a retry that
    inherited them would report a step as already done and skip it, which is
    how a "successful" run ends up built on a step that never ran twice.
    Approvals and policies carry over - a human already signed those off.
    """
    return ExecutionState(
        job_id=state.job_id,
        task=state.task,
        plan=plan or state.plan,
        user=state.user,
        roles=state.roles,
        document_ids=list(state.document_ids),
        approved_steps=set(state.approved_steps),
        data_policy=state.data_policy,
        tool_policy=state.tool_policy,
    )


def _plan_from_stored(stored: dict[str, Any]) -> Plan:
    payload = {key: value for key, value in stored.items() if key not in _PLAN_EXTRA_KEYS}
    return Plan.model_validate(payload)
