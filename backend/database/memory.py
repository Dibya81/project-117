"""Memory records (Phase 14).

Four kinds of memory, one table, because they differ in policy rather than in
shape:

``semantic``
    Durable facts about the plant: "C-101 is a reciprocating compressor".
    Must carry evidence - a fact without a source is a rumour.
``episodic``
    What happened in a job: the question asked, the plan taken, the outcome.
    Written by the system, never by a model.
``procedural``
    A sequence that worked and is worth repeating.
``organisational``
    Conventions and preferences that apply across sessions.

The rule that makes this safe: **a model cannot write memory directly.** The
memory service validates every candidate (kind, size, scope, evidence for
semantic claims) and records who wrote it and why. Otherwise memory becomes a
channel for laundering an unverified claim into a trusted store - it gets
remembered, retrieved later as fact, and cited with confidence.

``scope`` is the isolation boundary (``global``, ``user:<id>``,
``session:<id>``, ``document:<id>``) so a private session cannot silently
teach the whole workspace.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.models import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # semantic | episodic | procedural | organisational
    kind: Mapped[str] = mapped_column(String(24), index=True)
    # global | user:<id> | session:<id> | document:<id>
    scope: Mapped[str] = mapped_column(String(128), default="global", index=True)
    # Stable lookup key within a scope (equipment tag, job id, routine name).
    key: Mapped[str] = mapped_column(String(256), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    # Evidence for the claim: document_id, page, section, chunk_id. Required
    # for semantic records by the memory service.
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    # Who or what wrote it, and during which job.
    source: Mapped[str] = mapped_column(String(64), default="system")
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # 0.0-1.0. Retrieval prefers higher-confidence records; it does not treat
    # low confidence as false.
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    # Session-scoped memory expires; plant facts do not.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
