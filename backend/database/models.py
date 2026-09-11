"""ORM models.

Phase 1 persistence covers what the foundation needs: documents and audit
events. Each remaining table arrives with the phase that actually uses it —
jobs with the Phase 6 orchestrator state machine, artifacts with Phase 10
deliverables, users/sessions/messages with Phase 17.

Schema changes and pre-existing databases
-----------------------------------------
``init_db`` calls ``create_all``, which creates missing *tables* but never
ALTERs an existing one. Adding a column here therefore does nothing to a
database file that already exists, and queries fail with "no such column".
Until Alembic lands (Phase 17): delete ``data/project117.db`` (development
data only) or add the column by hand.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    filename: Mapped[str] = mapped_column(String(512))
    stored_name: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # stored -> indexing (Phase 3) -> indexed | failed
    status: Mapped[str] = mapped_column(String(32), default="stored")
    # Structured ingestion metadata (page/section/chunk provenance) lives here
    # from Phase 3 on. Never store raw document content in this column.
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    user: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Canonical vocabulary, validated on write by
    # backend.security.audit.audit_log.validate_outcome:
    #   success | failure | refused | pending
    # "refused" is a policy decision, not an outage; "pending" means the
    # operation parked at an approval gate and has not run.
    outcome: Mapped[str] = mapped_column(String(16), default="success")
    # Provenance (Phase 0.5). An audit row must answer "who ran what, with
    # which model, and who approved it" without joining anything else. These
    # exist before the Phase 7 approval gates and Phase 9 sandbox so those are
    # auditable the day they are written, not retrofitted afterwards.
    agent: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tool: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # not_required | pending | approved | rejected.
    # Defaults to not_required: defaulting to "approved" would forge consent
    # that nobody gave.
    approval: Mapped[str] = mapped_column(String(16), default="not_required", index=True)
    # Structured, non-sensitive detail (ids, sizes, durations). Never content.
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
