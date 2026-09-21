"""0001_baseline

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-09-21 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── documents table ──────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("stored_name", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="stored"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── audit_events table ───────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("agent", sa.String(length=128), nullable=True),
        sa.Column("tool", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("approval", sa.String(length=16), nullable=False, server_default="not_required"),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("chain_seq", sa.Integer(), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("current_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chain_seq"),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_agent"), "audit_events", ["agent"], unique=False)
    op.create_index(op.f("ix_audit_events_approval"), "audit_events", ["approval"], unique=False)
    op.create_index(op.f("ix_audit_events_chain_seq"), "audit_events", ["chain_seq"], unique=True)
    op.create_index(op.f("ix_audit_events_current_hash"), "audit_events", ["current_hash"], unique=False)
    op.create_index(op.f("ix_audit_events_resource_id"), "audit_events", ["resource_id"], unique=False)
    op.create_index(op.f("ix_audit_events_resource_type"), "audit_events", ["resource_type"], unique=False)
    op.create_index(op.f("ix_audit_events_timestamp"), "audit_events", ["timestamp"], unique=False)
    op.create_index(op.f("ix_audit_events_tool"), "audit_events", ["tool"], unique=False)

    # ── workspaces table ─────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("knowledge_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── knowledge_entities table ─────────────────────────────────────────
    op.create_table(
        "knowledge_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("rel_type", sa.String(length=128), nullable=True),
        sa.Column("target_name", sa.String(length=512), nullable=True),
        sa.Column("source_chunk", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_entities_document_id"), "knowledge_entities", ["document_id"], unique=False)
    op.create_index(op.f("ix_knowledge_entities_entity_type"), "knowledge_entities", ["entity_type"], unique=False)
    op.create_index(op.f("ix_knowledge_entities_name"), "knowledge_entities", ["name"], unique=False)
    op.create_index(op.f("ix_knowledge_entities_target_name"), "knowledge_entities", ["target_name"], unique=False)
    op.create_index(op.f("ix_knowledge_entities_workspace_id"), "knowledge_entities", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_table("knowledge_entities")
    op.drop_table("workspaces")
    op.drop_table("audit_events")
    op.drop_table("documents")
