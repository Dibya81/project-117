"""Audit service.

Every sensitive operation records an audit event: user, timestamp, action,
resource, agent, tool, model, approval, outcome, error. `detail` carries
structured, non-sensitive metadata (ids, sizes, durations) — never raw
document contents.

The agent/tool/model/approval fields exist from Phase 0.5 so that the Phase 7
approval gates and Phase 9 sandbox executions are auditable the day they are
written, rather than retrofitted afterwards.

Shaping, validation and redaction live in `audit_log`, which is importable
without a database driver. This module is only the persistence half: it turns a
canonical event into an `AuditEvent` row. Keeping the split means the rule
"an API key never reaches a permanent row" is testable without SQLAlchemy, and
that the in-memory store in `event_store` enforces exactly the same rule.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from backend.database.models import AuditEvent
from backend.security.audit.audit_log import (
    APPROVAL_STATES,
    MAX_DETAIL_CHARS,
    OUTCOME_ALIASES,
    OUTCOMES,
    AuditFieldError,
    canonical_event,
    log_event,
    redact_detail,
    serialise_detail,
    validate_approval,
    validate_outcome,
)
from backend.security.audit.event_store import (
    DEFAULT_CAPACITY,
    EventStore,
    InMemoryEventStore,
    StoredEvent,
)

logger = logging.getLogger(__name__)

__all__ = [
    "APPROVAL_STATES",
    "DEFAULT_CAPACITY",
    "MAX_DETAIL_CHARS",
    "OUTCOMES",
    "OUTCOME_ALIASES",
    "AuditFieldError",
    "AuditService",
    "EventStore",
    "InMemoryEventStore",
    "StoredEvent",
    "canonical_event",
    "log_event",
    "redact_detail",
    "serialise_detail",
    "validate_approval",
    "validate_outcome",
]


class AuditService:
    """Database-backed audit sink. Satisfies the `EventStore` intent, but
    returns ORM rows rather than `StoredEvent`, because callers filter on
    indexed columns.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user: str | None = None,
        outcome: str = "success",
        agent: str | None = None,
        tool: str | None = None,
        model: str | None = None,
        approval: str = "not_required",
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """Validate, redact and persist one audit event.

        `canonical_event` raises `AuditFieldError` for an unknown approval
        state or outcome, and passes `detail` through the secret redactor. That
        redaction is the reason this method does not serialise `detail` itself:
        doing so previously wrote the mapping verbatim, so anything a caller
        happened to include - a connector token in a request echo, an API key
        in an error payload - was persisted in clear text.
        """
        payload = canonical_event(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user=user,
            outcome=outcome,
            agent=agent,
            tool=tool,
            model=model,
            approval=approval,
            detail=detail,
            error=error,
        )
        event = AuditEvent(**payload)
        with self._session_factory() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        log_event(payload)
        return event

    def get(self, event_id: str) -> AuditEvent | None:
        with self._session_factory() as session:
            return session.get(AuditEvent, event_id)

    def list(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        approval: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        with self._session_factory() as session:
            stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
            if resource_type:
                stmt = stmt.where(AuditEvent.resource_type == resource_type)
            if resource_id:
                stmt = stmt.where(AuditEvent.resource_id == resource_id)
            if action:
                stmt = stmt.where(AuditEvent.action == action)
            if agent:
                stmt = stmt.where(AuditEvent.agent == agent)
            if tool:
                stmt = stmt.where(AuditEvent.tool == tool)
            if approval:
                stmt = stmt.where(AuditEvent.approval == approval)
            return list(session.scalars(stmt))
