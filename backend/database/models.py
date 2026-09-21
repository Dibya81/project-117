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

Knowledge Workspace additions (Phase KW)
-----------------------------------------
``Workspace`` and ``KnowledgeEntity`` tables are new; ``create_all`` will
create them on a fresh start or on the next start after the code lands.
``workspace_id`` for Documents is stored inside ``metadata_json`` to avoid
breaking the existing ``documents`` table schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
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
    # Phase KW additions stored here (no ALTER TABLE needed):
    #   metadata["workspace_id"]        — owning workspace
    #   metadata["checksum"]            — sha256 hex of the upload
    #   metadata["ingestion"]["stage"]  — current pipeline stage for SSE
    #   metadata["ingestion"]["stage_pct"]     — 0-100
    #   metadata["ingestion"]["stage_message"] — human-readable status
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
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

    # --- tamper-evident chain (Phase 2) -----------------------------------
    # Dense, ascending position in the hash chain. Ordering by `timestamp`
    # would be ambiguous for two events in the same second (and editable), so
    # the chain carries its own order. Nullable because rows written before
    # the chain existed are backfilled by
    # backend/security/audit/audit_chain.ensure_chain.
    chain_seq: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    # sha256 of the preceding row's current_hash, or the genesis constant.
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # sha256(previous_hash || canonical_json(row)); the exact serialisation
    # lives in backend/security/audit/audit_chain.py.
    current_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


# ---------------------------------------------------------------------------
# Company Knowledge Onboarding — Phase KW
# ---------------------------------------------------------------------------


class Workspace(Base):
    """A named knowledge workspace — a logical container for uploaded company
    documents, their vector index, and the knowledge graph derived from them.

    A fresh install starts with a single ``default`` workspace (created at
    first use). Additional workspaces allow teams to manage separate corpora
    without mixing document indexes.
    """

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Monotonically incrementing integer, bumped after every index or graph
    # update so the UI can show "knowledge version v7" and detect staleness.
    knowledge_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class KnowledgeEntity(Base):
    """A named entity and/or relationship extracted from an ingested document.

    Extraction is incremental: each newly indexed document contributes its own
    rows; no full rebuild is required for new uploads.

    Relationships are stored as directed edges: ``(entity_name, rel_type,
    target_name)``.  ``target_name`` is free text — it refers to another
    entity by name rather than by foreign key, so the graph can reference
    entities from other documents (or from the simulation dataset) without a
    cascade dependency.  The frontend join is done in Python/JS at query time.

    Provenance: every row links back to the ``document_id`` and
    ``source_chunk`` that produced it, so the UI can show
    "P-102  →  mentioned_in  →  Inspection_Report.pdf  (chunk 12)".
    """

    __tablename__ = "knowledge_entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    # e.g. "Equipment", "Sensor", "SOP", "WorkOrder", "Material", "Supplier"
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    # The canonical name of the entity as extracted from the document.
    name: Mapped[str] = mapped_column(String(512), index=True)
    # Optional alternative names, JSON array of strings.
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    # Relationship to another entity; null if this row is just an entity node.
    rel_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    # The chunk index within the document that produced this extraction.
    source_chunk: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Model confidence in [0, 1].
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
