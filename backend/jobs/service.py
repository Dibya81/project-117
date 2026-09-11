"""Job persistence and transitions (Phase 6).

This is the only module that writes ``jobs`` and ``job_events``. Everything
else - the API, the orchestrator, the approval endpoints - goes through here,
which is what makes the state machine in ``state.py`` an actual guarantee
rather than a diagram.

Three properties worth stating:

**Every transition is checked.** ``transition`` refuses an illegal move, so
``COMPLETED`` cannot be reached without passing through ``VERIFYING``, and a
terminal job cannot be resurrected.

**Every transition is recorded.** A row in ``job_events`` is written in the
same transaction as the state change, then published to the bus. Persist
first, notify second: a subscriber can miss a notification and still recover
the truth by replaying events.

**Concurrent advances are rejected, not merged.** ``jobs.version`` is checked
on update; the loser raises :class:`ConcurrentJobUpdate`. That is what stops
an approval arriving at the same moment as a timeout from producing a state
nobody intended.

The methods are synchronous because SQLAlchemy's session is. The orchestrator
calls them through ``asyncio.to_thread`` so the event loop is never blocked.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.database.execution import Job, JobEvent
from backend.jobs.bus import JobEventBus
from backend.jobs.state import (
    FAILURE_STATES,
    JobState,
    assert_transition,
    is_terminal,
    parse_state,
)

logger = logging.getLogger(__name__)

#: Truncation for free-text stored on the job. A task is a request, not a
#: document; anything longer is a sign that content is being smuggled in.
MAX_TASK_CHARS = 8000
MAX_ERROR_CHARS = 4000


class JobNotFound(LookupError):
    reason = "job_not_found"

    def __init__(self, job_id: str) -> None:
        super().__init__(f"job '{job_id}' does not exist")
        self.job_id = job_id


class ConcurrentJobUpdate(RuntimeError):
    """Another writer advanced this job first. Re-read before deciding."""

    reason = "job_conflict"

    def __init__(self, job_id: str) -> None:
        super().__init__(f"job '{job_id}' was modified concurrently")
        self.job_id = job_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return fallback


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_dict(job: Job) -> dict[str, Any]:
    """API/orchestrator view of a job. JSON columns arrive decoded."""
    return {
        "id": job.id,
        "kind": job.kind,
        "state": job.state,
        "task": job.task,
        "user": job.user,
        "session_id": job.session_id,
        "request": _loads(job.request_json, {}),
        "plan": _loads(job.plan_json, None),
        "result": _loads(job.result_json, None),
        "verification": _loads(job.verification_json, None),
        "approval": job.approval,
        "approval_request": _loads(job.approval_json, None),
        "approved_by": job.approved_by,
        "error": job.error,
        "version": job.version,
        "terminal": is_terminal(parse_state(job.state)),
        "created_at": _iso(job.created_at),
        "updated_at": _iso(job.updated_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


def _event_dict(event: JobEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "job_id": event.job_id,
        "sequence": event.sequence,
        "kind": event.kind,
        "state": event.state,
        "message": event.message,
        "detail": _loads(event.detail_json, {}),
        "created_at": _iso(event.created_at),
    }


class JobService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        bus: JobEventBus | None = None,
    ) -> None:
        self._sessions = session_factory
        self._bus = bus

    # --- creation and reads ----------------------------------------------

    def create(
        self,
        *,
        task: str,
        kind: str = "chat",
        user: str | None = None,
        session_id: str | None = None,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._sessions() as session:
            job = Job(
                kind=kind,
                state=JobState.QUEUED.value,
                task=(task or "")[:MAX_TASK_CHARS],
                user=user,
                session_id=session_id,
                request_json=json.dumps(request or {}, default=str),
            )
            session.add(job)
            session.flush()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job.id,
                kind="state",
                state=JobState.QUEUED.value,
                message="job accepted",
                detail={"kind": kind},
            )
            session.commit()
        self._publish(payload["id"], event)
        return payload

    def get(self, job_id: str) -> dict[str, Any]:
        with self._sessions() as session:
            return _job_dict(self._require(session, job_id))

    def list(
        self,
        *,
        user: str | None = None,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._sessions() as session:
            statement = select(Job).order_by(Job.created_at.desc())
            if user:
                statement = statement.where(Job.user == user)
            if state:
                statement = statement.where(Job.state == parse_state(state).value)
            rows = session.execute(statement.limit(limit).offset(max(0, offset))).scalars()
            return [_job_dict(job) for job in rows]

    def events(self, job_id: str, *, after: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """Persisted progress, for replay before following the live stream."""
        with self._sessions() as session:
            self._require(session, job_id)
            statement = (
                select(JobEvent)
                .where(JobEvent.job_id == job_id, JobEvent.sequence > after)
                .order_by(JobEvent.sequence.asc())
                .limit(max(1, min(limit, 1000)))
            )
            return [_event_dict(event) for event in session.execute(statement).scalars()]

    # --- transitions ------------------------------------------------------

    def transition(
        self,
        job_id: str,
        target: JobState,
        *,
        message: str = "",
        detail: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        with self._sessions() as session:
            job = self._require(session, job_id)
            if expected_version is not None and job.version != expected_version:
                raise ConcurrentJobUpdate(job_id)
            current = parse_state(job.state)
            if current is target and target is JobState.EXECUTING:
                # Legal and common: the next step of a multi-step plan.
                pass
            assert_transition(current, target)
            job.state = target.value
            job.version += 1
            job.updated_at = _utcnow()
            if target is JobState.PLANNING and job.started_at is None:
                job.started_at = _utcnow()
            if is_terminal(target):
                job.finished_at = _utcnow()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="state",
                state=target.value,
                message=message or f"state -> {target.value}",
                detail=detail or {},
            )
            session.commit()
        self._publish(job_id, event)
        if is_terminal(target) and self._bus is not None:
            self._bus.close(job_id)
        return payload

    def progress(
        self,
        job_id: str,
        *,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a note without changing state ("retrieved 14 chunks")."""
        with self._sessions() as session:
            job = self._require(session, job_id)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="progress",
                state=job.state,
                message=message,
                detail=detail or {},
            )
            session.commit()
        self._publish(job_id, event)
        return event

    def set_plan(self, job_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        with self._sessions() as session:
            job = self._require(session, job_id)
            job.plan_json = json.dumps(plan, default=str)
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            session.commit()
        return payload

    def set_result(
        self,
        job_id: str,
        *,
        result: dict[str, Any],
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store the result. Does **not** mark the job successful.

        Completion is a separate transition that only the verification stage
        performs, so a stored result can never imply a verified one.
        """
        with self._sessions() as session:
            job = self._require(session, job_id)
            job.result_json = json.dumps(result, default=str)
            if verification is not None:
                job.verification_json = json.dumps(verification, default=str)
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            session.commit()
        return payload

    def fail(
        self,
        job_id: str,
        *,
        error: str,
        state: JobState = JobState.FAILED,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state not in FAILURE_STATES:
            raise ValueError(f"{state.value} is not a failure state")
        with self._sessions() as session:
            job = self._require(session, job_id)
            current = parse_state(job.state)
            if is_terminal(current):
                # Already finished; do not rewrite history.
                return _job_dict(job)
            assert_transition(current, state)
            job.state = state.value
            job.error = (error or "")[:MAX_ERROR_CHARS]
            job.version += 1
            job.finished_at = _utcnow()
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="error",
                state=state.value,
                message=job.error or state.value,
                detail=detail or {},
            )
            session.commit()
        self._publish(job_id, event)
        if self._bus is not None:
            self._bus.close(job_id)
        return payload

    def cancel(self, job_id: str, *, reason: str = "cancelled") -> dict[str, Any]:
        return self.fail(job_id, error=reason, state=JobState.CANCELLED)

    def timeout(self, job_id: str, *, reason: str = "job timed out") -> dict[str, Any]:
        return self.fail(job_id, error=reason, state=JobState.TIMEOUT)

    # --- approval ---------------------------------------------------------

    def request_approval(
        self,
        job_id: str,
        *,
        request: dict[str, Any],
        message: str = "approval required",
    ) -> dict[str, Any]:
        """Park the job. Called *before* the gated action happens."""
        with self._sessions() as session:
            job = self._require(session, job_id)
            assert_transition(parse_state(job.state), JobState.NEEDS_APPROVAL)
            job.state = JobState.NEEDS_APPROVAL.value
            job.approval = "pending"
            job.approval_json = json.dumps(request, default=str)
            job.version += 1
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="approval",
                state=job.state,
                message=message,
                detail=request,
            )
            session.commit()
        self._publish(job_id, event)
        return payload

    def approve(
        self,
        job_id: str,
        *,
        user: str | None,
        note: str = "",
    ) -> dict[str, Any]:
        """Grant approval and hand the job back to EXECUTING.

        Only recorded here; the orchestrator resumes from the parked step. An
        approval on a job that is not parked is a conflict, not a no-op -
        silently accepting it would let a client approve future actions.
        """
        with self._sessions() as session:
            job = self._require(session, job_id)
            if parse_state(job.state) is not JobState.NEEDS_APPROVAL:
                raise ConcurrentJobUpdate(job_id)
            job.approval = "approved"
            job.approved_by = user
            job.state = JobState.EXECUTING.value
            job.version += 1
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="approval",
                state=job.state,
                message=note or "approved",
                detail={"approved_by": user},
            )
            session.commit()
        self._publish(job_id, event)
        return payload

    def reject(
        self,
        job_id: str,
        *,
        user: str | None,
        reason: str = "rejected by reviewer",
    ) -> dict[str, Any]:
        with self._sessions() as session:
            job = self._require(session, job_id)
            if parse_state(job.state) is not JobState.NEEDS_APPROVAL:
                raise ConcurrentJobUpdate(job_id)
            job.approval = "rejected"
            job.approved_by = user
            job.state = JobState.CANCELLED.value
            job.error = reason[:MAX_ERROR_CHARS]
            job.version += 1
            job.finished_at = _utcnow()
            job.updated_at = _utcnow()
            payload = _job_dict(job)
            event = self._append_event(
                session,
                job_id=job_id,
                kind="approval",
                state=job.state,
                message=reason,
                detail={"rejected_by": user},
            )
            session.commit()
        self._publish(job_id, event)
        if self._bus is not None:
            self._bus.close(job_id)
        return payload

    # --- internals --------------------------------------------------------

    def _require(self, session: Session, job_id: str) -> Job:
        job = session.get(Job, job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def _append_event(
        self,
        session: Session,
        *,
        job_id: str,
        kind: str,
        state: str | None,
        message: str,
        detail: dict[str, Any],
    ) -> dict[str, Any]:
        highest = session.execute(
            select(func.max(JobEvent.sequence)).where(JobEvent.job_id == job_id)
        ).scalar()
        event = JobEvent(
            job_id=job_id,
            sequence=int(highest or 0) + 1,
            kind=kind,
            state=state,
            message=message[:2000],
            detail_json=json.dumps(detail, default=str),
        )
        session.add(event)
        session.flush()
        return _event_dict(event)

    def _publish(self, job_id: str, event: dict[str, Any]) -> None:
        if self._bus is None:
            return
        try:
            self._bus.publish(job_id, event)
        except Exception:  # pragma: no cover - notification must never fail work
            logger.warning("failed to publish event for job %s", job_id, exc_info=True)
