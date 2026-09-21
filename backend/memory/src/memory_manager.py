"""Memory service (Phase 13).

The gate this module exists to enforce: a model proposes a memory candidate,
this service decides whether it is admissible, and only admissible records
ever reach the ``memory_records`` table. Nothing downstream (recall, the
context pack, a future answer) can tell the difference between a fact that
was checked and one that was not, so the checking has to happen exactly
once, here, before the row is written.

Admission rules, in order:

1. **kind** must be one of the four defined kinds. An unknown kind is not a
   new feature, it is a bug in whatever proposed it.
2. **semantic claims require evidence.** A durable "fact about the plant"
   with no ``evidence`` entry is indistinguishable from a hallucination that
   got remembered; refuse it outright rather than store it at low
   confidence.
3. **size limits.** ``content`` is capped so memory cannot become a second,
   ungoverned document store.
4. **scope must parse.** ``global``, ``user:<id>``, ``session:<id>`` or
   ``document:<id>`` - anything else is refused rather than silently
   downgraded to global, which would leak a session-local note workspace
   wide.

Recall is deliberately dumb: keyword overlap against ``key``/``content``,
scoped and ranked by confidence and recency. This is not semantic search -
that is what the RAG retrieval service is for. Memory recall answers "has
this specific thing been noted before", not "what documents are relevant".
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.database.memory import MemoryRecord

logger = logging.getLogger(__name__)

MEMORY_KINDS = frozenset({"semantic", "episodic", "procedural", "organisational"})

#: Written by the system on the job's behalf, never attributed to a model as
#: if the model itself had an account.
SOURCE_SYSTEM = "system"
#: A model *proposed* this record; it was still checked and admitted here.
SOURCE_MODEL_PROPOSED = "model_proposed"

MAX_CONTENT_CHARS = 4000
MAX_KEY_CHARS = 256
#: Session-scoped memory is useful for exactly one conversation; expire it
#: rather than let a stale, ungoverned note accumulate forever.
DEFAULT_SESSION_TTL_HOURS = 72

_SCOPE_PATTERN = re.compile(r"^(global|user:[\w.\-@]+|session:[\w.\-]+|document:[\w.\-]+)$")
_WORD_PATTERN = re.compile(r"[a-z0-9]+")


class MemoryError(RuntimeError):
    reason = "memory_error"


class MemoryRejected(MemoryError):
    """A candidate failed admission. Distinct from a plumbing failure so the
    caller (an agent's memory-write step) can tell "you asked for something
    not allowed" apart from "the database is down"."""

    reason = "memory_rejected"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tokenize(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall((text or "").lower()))


def _record_to_dict(record: MemoryRecord) -> dict[str, Any]:
    try:
        evidence = json.loads(record.evidence_json or "[]")
    except (TypeError, ValueError):
        evidence = []
    try:
        metadata = json.loads(record.metadata_json or "{}")
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": record.id,
        "kind": record.kind,
        "scope": record.scope,
        "key": record.key,
        "content": record.content,
        "evidence": evidence,
        "source": record.source,
        "job_id": record.job_id,
        "user": record.user,
        "confidence": record.confidence,
        "metadata": metadata,
        "hits": record.hits,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
    }


class MemoryService:
    """The only writer of ``memory_records``. See module docstring for the
    admission rules that make this safe to expose to agents."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        audit: Any = None,
    ) -> None:
        self._sessions = session_factory
        self._audit = audit

    # --- writing ------------------------------------------------------

    def remember(
        self,
        *,
        kind: str,
        key: str,
        content: str,
        scope: str = "global",
        evidence: list[dict[str, Any]] | None = None,
        source: str = SOURCE_SYSTEM,
        job_id: str | None = None,
        user: str | None = None,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
        ttl_hours: float | None = None,
    ) -> dict[str, Any]:
        """Admit a candidate, or raise :class:`MemoryRejected`. See the
        module docstring for the four checks applied, in order."""
        kind = (kind or "").strip().lower()
        if kind not in MEMORY_KINDS:
            raise MemoryRejected(
                f"unknown memory kind '{kind}'; must be one of {sorted(MEMORY_KINDS)}"
            )
        if kind == "semantic" and not evidence:
            raise MemoryRejected(
                "semantic memory requires evidence (document_id/page/chunk_id); "
                "a durable fact with no source is not admissible"
            )
        key = (key or "").strip()[:MAX_KEY_CHARS]
        if not key:
            raise MemoryRejected("memory key must not be empty")
        content = (content or "").strip()
        if not content:
            raise MemoryRejected("memory content must not be empty")
        if len(content) > MAX_CONTENT_CHARS:
            raise MemoryRejected(
                f"memory content exceeds {MAX_CONTENT_CHARS} chars; "
                "summarise before writing, memory is not document storage"
            )
        scope = (scope or "global").strip()
        if not _SCOPE_PATTERN.match(scope):
            raise MemoryRejected(
                f"invalid scope '{scope}'; expected global, user:<id>, "
                "session:<id>, or document:<id>"
            )
        confidence = max(0.0, min(1.0, float(confidence)))

        expires_at = None
        if ttl_hours is not None:
            expires_at = _utcnow() + timedelta(hours=max(0.0, ttl_hours))
        elif scope.startswith("session:"):
            # Session memory defaults to expiring; nothing about a single
            # conversation should become a durable workspace fact for free.
            expires_at = _utcnow() + timedelta(hours=DEFAULT_SESSION_TTL_HOURS)

        with self._sessions() as session:
            record = MemoryRecord(
                kind=kind,
                scope=scope,
                key=key,
                content=content,
                evidence_json=json.dumps(evidence or [], default=str),
                source=source,
                job_id=job_id,
                user=user,
                confidence=confidence,
                metadata_json=json.dumps(metadata or {}, default=str),
                expires_at=expires_at,
            )
            session.add(record)
            session.flush()
            payload = _record_to_dict(record)
            session.commit()

        self._record_audit(
            action="memory.remember",
            resource_id=payload["id"],
            user=user,
            outcome="success",
            detail={"kind": kind, "scope": scope, "key": key, "source": source},
        )
        return payload

    def forget(self, memory_id: str, *, user: str | None = None) -> None:
        """Hard delete. Memory is a working store, not an audit log - the
        audit log (a separate table) keeps the fact that this was forgotten
        and by whom, even after the row itself is gone."""
        with self._sessions() as session:
            record = session.get(MemoryRecord, memory_id)
            if record is None:
                return
            session.delete(record)
            session.commit()
        self._record_audit(
            action="memory.forget",
            resource_id=memory_id,
            user=user,
            outcome="success",
        )

    def expire_stale(self) -> int:
        """Delete records past their ``expires_at``. Meant to be called from
        a periodic maintenance task, not from the request path."""
        now = _utcnow()
        with self._sessions() as session:
            statement = select(MemoryRecord).where(
                MemoryRecord.expires_at.is_not(None), MemoryRecord.expires_at <= now
            )
            rows = list(session.execute(statement).scalars())
            for row in rows:
                session.delete(row)
            session.commit()
        if rows:
            logger.info("memory: expired %d stale record(s)", len(rows))
        return len(rows)

    # --- reading --------------------------------------------------------

    def get(self, memory_id: str) -> dict[str, Any] | None:
        with self._sessions() as session:
            record = session.get(MemoryRecord, memory_id)
            return _record_to_dict(record) if record else None

    def list(
        self,
        *,
        kind: str | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._sessions() as session:
            statement = select(MemoryRecord).order_by(MemoryRecord.updated_at.desc())
            if kind:
                statement = statement.where(MemoryRecord.kind == kind)
            if scope:
                statement = statement.where(MemoryRecord.scope == scope)
            rows = session.execute(statement.limit(limit).offset(max(0, offset))).scalars()
            return [_record_to_dict(row) for row in rows]

    def recall(
        self,
        query: str,
        *,
        user: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Keyword-overlap recall scoped to global + this user + this
        session. See the module docstring for why this is not semantic
        search. Called by :class:`ContextManager` on every turn, so it must
        stay cheap: one bounded query, ranking done in Python on a capped
        candidate set, never an unbounded table scan."""
        query_words = _tokenize(query)
        if not query_words:
            return []

        scopes = ["global"]
        if user:
            scopes.append(f"user:{user}")
        if session_id:
            scopes.append(f"session:{session_id}")

        now = _utcnow()
        with self._sessions() as session:
            statement = (
                select(MemoryRecord)
                .where(MemoryRecord.scope.in_(scopes))
                .where((MemoryRecord.expires_at.is_(None)) | (MemoryRecord.expires_at > now))
                .order_by(MemoryRecord.confidence.desc(), MemoryRecord.updated_at.desc())
                .limit(200)
            )
            candidates = list(session.execute(statement).scalars())

            scored: list[tuple[float, MemoryRecord]] = []
            for record in candidates:
                haystack = _tokenize(f"{record.key} {record.content}")
                overlap = len(query_words & haystack)
                if overlap == 0:
                    continue
                # Overlap ratio against the query, so a short exact match on
                # the key outranks a long record that happens to share one
                # word.
                relevance = overlap / len(query_words)
                scored.append((relevance * (0.5 + record.confidence), record))

            scored.sort(key=lambda pair: pair[0], reverse=True)
            top = scored[: max(1, limit)]
            for _, record in top:
                record.hits += 1
            session.commit()
            return [_record_to_dict(record) for _, record in top]

    # --- internals --------------------------------------------------------

    def _record_audit(self, **kwargs: Any) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(**kwargs)
        except Exception as exc:  # bookkeeping never blocks the write it describes
            logger.warning("memory: failed to write audit event: %s", exc)
