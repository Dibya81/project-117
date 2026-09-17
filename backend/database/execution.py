"""Execution-side tables: jobs, job events, tool executions, artifacts.

These arrive with Phase 6-10, following the rule stated in ``models.py``:
a table lands with the phase that uses it, not in advance.

Why these four:

``jobs``
    A request that plans, retrieves, executes and gets verified outlives the
    HTTP connection that started it. Its state has to be durable so a client
    can reconnect, and so an approval can be granted minutes later.

``job_events``
    The database is the source of truth for progress; the event bus is only a
    notification. A client that connects late replays these by ``sequence``
    and misses nothing.

``tool_executions``
    Every registry call - including the rejected ones - lands here with its
    risk level and approval state. "Which tool ran, on whose authority, with
    what arguments (redacted), for how long" is answerable without reading
    application logs.

``artifacts``
    A deliverable is not a file path. It is bytes with a sha256, produced by a
    identified sandbox execution, in a known verification state. Downloads
    consult this row, so an unverified artifact cannot be quietly served as if
    it had passed.

Content rule, enforced by convention and by the redaction in the tool
registry: these tables hold identifiers, sizes, durations and statuses. Never
document text, never model output, never code.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.models import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # chat | agent | workflow | tool - which entry point created the job.
    kind: Mapped[str] = mapped_column(String(32), default="chat", index=True)
    # A value of backend.jobs.state.JobState.
    state: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    task: Mapped[str] = mapped_column(Text, default="")
    user: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Request parameters as submitted (document filter, workflow name, roles).
    request_json: Mapped[str] = mapped_column(Text, default="{}")
    # The plan, plus which steps are approved and where it is parked.
    plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # not_required | pending | approved | rejected (mirrors AuditEvent).
    approval: Mapped[str] = mapped_column(String(16), default="not_required", index=True)
    approval_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optimistic concurrency. Two workers (or a worker and an approval call)
    # must not both advance the same job; the loser retries or gives up rather
    # than writing a state that skipped a transition.
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    # Monotonic per job. Lets a reconnecting client say "everything after 12".
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    # state | progress | approval | error
    kind: Mapped[str] = mapped_column(String(32), default="progress")
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool: Mapped[str] = mapped_column(String(64), index=True)
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # ok | error | timeout | denied | invalid_arguments | awaiting_approval
    status: Mapped[str] = mapped_column(String(32), default="ok", index=True)
    risk: Mapped[str] = mapped_column(String(16), default="read")
    approval: Mapped[str] = mapped_column(String(16), default="not_required")
    # Redacted arguments (see backend.tools.registry.redact_arguments).
    arguments_json: Mapped[str] = mapped_column(Text, default="{}")
    sandbox_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # pptx | docx | xlsx | pdf
    type: Mapped[str] = mapped_column(String(16), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    # Computed on the bytes that left the sandbox and re-checked before a
    # download. A mismatch means the file changed after verification.
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    sandbox_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # pending | verified | verified_with_warnings | rejected | unverified
    # 'unverified' is distinct from 'pending': pending means verification has
    # not run yet, unverified means it cannot run here (no verifier wired).
    # Neither may be presented to a user as a verified artifact.
    verification_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    verification_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- Ed25519 signature (Phase 2) --------------------------------------
    # The SHA-256 above proves the file did not change; the signature proves
    # *nobody substituted it*, which needs a key the database owner does not
    # have. 'signed' | 'unsigned' | 'signature_failed' - 'unsigned' is a real
    # state and is reported as one, never dressed up as verified.
    signature_status: Mapped[str] = mapped_column(
        String(32), default="unsigned", index=True
    )
    signature_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    signature_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    spec_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
