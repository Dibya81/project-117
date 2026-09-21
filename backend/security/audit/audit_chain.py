"""Tamper-evident hash chain over the durable audit log.

Why this exists
---------------
The audit log was durable but not tamper-evident. ``audit_events`` is SQLite on
the same disk as everything else, so anyone who can run ``sqlite3`` can
``UPDATE audit_events SET outcome='success' WHERE ...`` or delete a row, and
nothing in the system notices. Durability is not integrity: a rewritten history
is still a history that reads as complete.

This module adds the missing property. Every row is linked to the one before it:

    current_hash = sha256(previous_hash || canonical_row)

so changing, inserting or removing any row breaks every link after it.

Design decisions, each of which is a place this could have been dishonest
-----------------------------------------------------------------------
**Genesis is a real row, not a magic constant.** The first row in a chain
carries ``previous_hash = GENESIS`` where ``GENESIS`` is the SHA-256 of a fixed,
documented string. Starting the chain from a constant rather than from an
existing row's hash means the chain has to *name its own beginning*: a verifier
can tell "this is the start of the log" apart from "the rows before this one
were deleted", because the latter leaves a row whose ``previous_hash`` is a hash
that no row in the chain produced.

**Ordering is explicit, not by timestamp.** ``chain_seq`` is a dense integer
assigned on append. Ordering by ``timestamp`` would have been ambiguous — two
events in the same second have no defined order — and, worse, an attacker could
reorder rows *and* their hashes consistently if the order itself were derived
from a mutable column.

**Existing rows are migrated, never dropped.** A database written before this
module existed has rows with NULL chain columns. :func:`ensure_chain` adds the
missing columns and backfills every historical row in a single transaction,
oldest first, so the *real* history is preserved and verifiable. The
alternative — declaring a fresh genesis and treating everything before it as
"pre-chain" — would leave the most interesting rows (whatever happened before
the upgrade) outside the tamper-evident region. Rows that already carry a hash
are left exactly as they are, so migration is idempotent and can never rewrite
a link that is already there.

**What this does and does not prove.** It detects modification, insertion,
deletion and reordering of rows *in the table*. It does not detect an attacker
who rewrites the whole chain from genesis — they need only recompute every hash,
because there is no secret in the chain and no external anchor. That is a
deliberate, stated limitation, not an oversight: the mitigation is signing the
chain head with the artifact-signing key (``backend.security.signing``) or
anchoring ``last_hash`` somewhere the database owner cannot reach, and neither
is done here. This is tamper-*evident* against the realistic threat (an
operator or process editing rows) and not tamper-*proof* against someone who
owns the file. Do not read a green verifier as more than that.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

logger = logging.getLogger("backend.audit.chain")

#: The ``previous_hash`` of the first row in a chain. The SHA-256 of a fixed
#: sentence rather than an empty string, so a row with a blank/zero hash is
#: visibly wrong instead of accidentally looking like a genesis row.
GENESIS_SENTENCE = "project117-audit-chain-genesis-v1"
GENESIS_HASH = hashlib.sha256(GENESIS_SENTENCE.encode("utf-8")).hexdigest()

#: Columns the chain adds to ``audit_events``.
CHAIN_COLUMNS: dict[str, str] = {
    "chain_seq": "INTEGER",
    "previous_hash": "TEXT",
    "current_hash": "TEXT",
}

#: The fields hashed into ``current_hash``, in this order. Every column that
#: describes the event is included; if a field is not here, editing it is not
#: detected, so this list is the security boundary and not a convenience.
HASHED_FIELDS: tuple[str, ...] = (
    "id",
    "timestamp",
    "user",
    "action",
    "resource_type",
    "resource_id",
    "outcome",
    "agent",
    "tool",
    "model",
    "approval",
    "detail_json",
    "error",
)

#: Guards append and migration in-process. SQLite serialises writers across
#: processes, but the read-max-then-insert in :func:`append_link` is not atomic
#: in Python, and a fork in the chain is unrecoverable without a rewrite.
#: :func:`chain_transaction` holds it across the caller's INSERT and COMMIT so
#: two concurrent requests cannot both read the same head.
_LOCK = threading.RLock()


def chain_transaction() -> threading.RLock:
    """The lock an append must hold from link computation through COMMIT.

    Exposed so the audit service can wrap ``compute`` + ``insert`` + ``commit``
    as one critical section. Without it the window between reading the head and
    writing the row is long enough for a second request to fork the chain, and
    a forked chain cannot be repaired without rewriting hashes.
    """
    return _LOCK


def _utc_iso(value: Any) -> Any:
    """Normalise a timestamp to naive-UTC ISO-8601.

    SQLite has no timezone type: SQLAlchemy returns a naive ``datetime`` for a
    value written from an aware one, and the raw driver returns the stored
    string. Hashing the repr of a ``datetime`` would therefore produce a
    different digest depending on whether the row was read through the ORM or
    through ``sqlite3`` — and the verifier must not depend on which door it came
    through. Everything is normalised here, once.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat(sep=" ")
    return str(value)


def canonical_payload(row: Mapping[str, Any], chain_seq: int) -> dict[str, Any]:
    """The exact mapping that is hashed for one row.

    ``chain_seq`` is inside the hash: without it, two identical events at the
    same position could swap places without detection.
    """
    payload: dict[str, Any] = {"chain_seq": chain_seq}
    for name in HASHED_FIELDS:
        value = row.get(name)
        payload[name] = _utc_iso(value) if name == "timestamp" else value
    return payload


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Deterministic serialisation: sorted keys, no whitespace ambiguity."""
    return json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))


def link_hash(previous_hash: str, payload: Mapping[str, Any]) -> str:
    """``sha256(previous_hash || canonical_serialisation_of_the_row)``."""
    material = f"{previous_hash}{canonical_json(payload)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_hash(row: Mapping[str, Any], previous_hash: str, chain_seq: int) -> str:
    return link_hash(previous_hash, canonical_payload(row, chain_seq))


# --------------------------------------------------------------------- schema


def chain_columns_present(db_path: str | Path) -> bool:
    """True when every chain column exists on ``audit_events``."""
    import sqlite3

    try:
        with sqlite3.connect(str(db_path)) as conn:
            names = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
    except sqlite3.DatabaseError:
        return False
    return bool(names) and set(CHAIN_COLUMNS) <= names


def _add_missing_columns(conn: Any) -> list[str]:
    """``ALTER TABLE ADD COLUMN`` for anything missing. Returns what it added.

    ``create_all`` creates missing *tables* but never alters an existing one, so
    a database file written before this module existed needs this. Adding a
    nullable column is the one migration SQLite performs without a table
    rewrite, which is what makes it safe to do at startup on a live file.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
    added: list[str] = []
    for name, decl in CHAIN_COLUMNS.items():
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE audit_events ADD COLUMN {name} {decl}")
        added.append(name)
    if "chain_seq" in added:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_audit_events_chain_seq "
            "ON audit_events (chain_seq)"
        )
    return added


def _order_clause(columns: set[str], *, descending: bool = False) -> str:
    """Deterministic row order.

    Ordered by ``rowid`` where available: it is the insertion order SQLite
    always had, and for an audit log that is the real event order. It is also
    stable against equal timestamps. Falls back to ``(timestamp, id)`` for a
    schema without an implicit rowid.
    """
    if "chain_seq" in columns:
        return f"ORDER BY chain_seq {'DESC' if descending else 'ASC'}"
    return f"ORDER BY timestamp {'DESC' if descending else 'ASC'}, id"


@dataclass
class ChainState:
    """Where a chain currently ends."""

    last_hash: str = GENESIS_HASH
    last_seq: int = 0
    events: int = 0
    migrated: int = 0
    columns_added: list[str] = field(default_factory=list)


def ensure_chain(db_path: str | Path) -> ChainState:
    """Make ``audit_events`` chainable, backfilling history exactly once.

    Returns the state an append should continue from. Safe to call on every
    startup and on every append: it is a no-op once the schema is present and
    no row is left unchained.
    """
    import sqlite3

    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        conn = sqlite3.connect(str(path), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'"
            ).fetchone()
            if table is None:
                # No audit table yet. Nothing to migrate; the ORM creates it.
                return ChainState()
            added = _add_missing_columns(conn)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
            state = _backfill(conn, columns)
            state.columns_added = added
            conn.commit()
        finally:
            conn.close()
    if state.migrated:
        logger.info(
            "audit chain: linked %d pre-existing audit row(s) into the chain",
            state.migrated,
        )
    return state


def _backfill(conn: Any, columns: set[str]) -> ChainState:
    """Assign chain links to every row that has none, oldest first."""
    cursor = conn.execute(f"SELECT rowid, * FROM audit_events {_order_clause(columns)}")
    names = [description[0] for description in cursor.description]
    rows = [dict(zip(names, row)) for row in cursor]

    chained = [row for row in rows if row["chain_seq"] is not None]
    unchained = [row for row in rows if row["chain_seq"] is None]

    last_hash = GENESIS_HASH
    last_seq = 0
    if chained:
        # A partially chained log: continue from the real end of the chain
        # rather than from genesis, or the backfilled rows would form a second
        # chain that the verifier would reject.
        head = chained[-1]
        last_hash = head["current_hash"] or GENESIS_HASH
        last_seq = int(head["chain_seq"])

    migrated = 0
    for row in unchained:
        seq = last_seq + 1
        current = compute_hash(row, last_hash, seq)
        conn.execute(
            "UPDATE audit_events SET chain_seq = ?, previous_hash = ?, current_hash = ? "
            "WHERE rowid = ?",
            (seq, last_hash, current, row["rowid"]),
        )
        last_hash, last_seq, migrated = current, seq, migrated + 1

    return ChainState(
        last_hash=last_hash,
        last_seq=last_seq,
        events=len(rows),
        migrated=migrated,
    )


def append_link(conn: Any, row: Mapping[str, Any]) -> tuple[int, str, str]:
    """Assign and return ``(chain_seq, previous_hash, current_hash)`` for a new row.

    Called inside the caller's transaction, immediately before the INSERT, so
    the link is part of the same commit as the row it describes. A crash
    between the two is therefore impossible: there is no window in which a row
    exists without its link.
    """
    with _LOCK:
        cursor = conn.execute(
            "SELECT chain_seq, current_hash FROM audit_events "
            "WHERE chain_seq IS NOT NULL ORDER BY chain_seq DESC LIMIT 1"
        )
        head = cursor.fetchone()
        last_seq = int(head[0]) if head and head[0] is not None else 0
        last_hash = head[1] if head and head[1] else GENESIS_HASH
        seq = last_seq + 1
        current = compute_hash(row, last_hash, seq)
        return seq, last_hash, current


# ------------------------------------------------------------------- verify


@dataclass
class ChainVerification:
    """The result of walking the chain.

    ``valid`` is the whole answer; every other field exists so a failure names
    the row and the reason instead of just saying "no".
    """

    valid: bool
    events: int
    last_hash: str
    last_seq: int
    #: The first row that failed to verify.
    broken_id: str | None = None
    broken_seq: int | None = None
    reason: str | None = None
    checked_at: str | None = None
    #: Set when the verifier could not run at all (no table, bad file). Kept
    #: distinct from ``valid False``: "unchecked" is not "intact", and the two
    #: must never be collapsed into a green light.
    error: str | None = None

    @property
    def status(self) -> str:
        if self.error:
            return "UNVERIFIABLE"
        return "VALID" if self.valid else "BROKEN"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "valid": self.valid,
            "status": self.status,
            "events": self.events,
            "last_hash": self.last_hash,
            "last_seq": self.last_seq,
            "checked_at": self.checked_at,
            "algorithm": "sha256(previous_hash || canonical_json(row))",
            "genesis_hash": GENESIS_HASH,
        }
        if self.broken_id is not None:
            payload["broken_id"] = self.broken_id
            payload["broken_seq"] = self.broken_seq
            payload["reason"] = self.reason
        if self.error is not None:
            payload["error"] = self.error
        return payload


def verify_chain(db_path: str | Path) -> ChainVerification:
    """Walk the chain oldest-first and report the first broken link.

    Four things are checked per row, because each corresponds to a distinct way
    of editing the log:

    1. ``chain_seq`` is dense and ascending — a deleted row leaves a gap.
    2. ``previous_hash`` equals the previous row's ``current_hash`` — a deleted,
       inserted or reordered row breaks the link.
    3. the recomputed hash equals the stored ``current_hash`` — an edited field
       changes the digest.
    4. the first row really is genesis — rows removed from the front would
       otherwise leave a chain that verifies from wherever it now starts.
    """
    import sqlite3

    checked_at = datetime.now(timezone.utc).isoformat()
    path = Path(db_path)
    if str(path) != ":memory:" and not path.exists():
        return ChainVerification(
            valid=False,
            events=0,
            last_hash=GENESIS_HASH,
            last_seq=0,
            error=f"audit database not found at {path}",
            checked_at=checked_at,
        )

    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'"
        ).fetchone()
        if table is None:
            return ChainVerification(
                valid=False,
                events=0,
                last_hash=GENESIS_HASH,
                last_seq=0,
                error="the audit_events table does not exist",
                checked_at=checked_at,
            )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
        missing = set(CHAIN_COLUMNS) - columns
        if missing:
            return ChainVerification(
                valid=False,
                events=0,
                last_hash=GENESIS_HASH,
                last_seq=0,
                error=(
                    "the audit table has no chain columns ("
                    + ", ".join(sorted(missing))
                    + "); run ensure_chain() first"
                ),
                checked_at=checked_at,
            )

        cursor = conn.execute(f"SELECT * FROM audit_events {_order_clause(columns)}")
        names = [description[0] for description in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor]

        if not rows:
            return ChainVerification(
                valid=True,
                events=0,
                last_hash=GENESIS_HASH,
                last_seq=0,
                checked_at=checked_at,
            )

        expected_prev = GENESIS_HASH
        expected_seq = 1
        for index, row in enumerate(rows):
            row_id = str(row.get("id"))
            seq = row.get("chain_seq")
            if seq is None:
                return ChainVerification(
                    valid=False,
                    events=len(rows),
                    last_hash=expected_prev,
                    last_seq=index,
                    broken_id=row_id,
                    broken_seq=None,
                    reason=(
                        "row is not part of the chain (chain_seq is NULL); the row was "
                        "inserted without going through the audit service"
                    ),
                    checked_at=checked_at,
                )
            seq = int(seq)
            if seq != expected_seq:
                return ChainVerification(
                    valid=False,
                    events=len(rows),
                    last_hash=expected_prev,
                    last_seq=seq - 1,
                    broken_id=row_id,
                    broken_seq=seq,
                    reason=(
                        f"chain_seq jumped from {expected_seq - 1} to {seq}; "
                        "row(s) were removed from or inserted into the chain"
                    ),
                    checked_at=checked_at,
                )
            stored_prev = row.get("previous_hash")
            if stored_prev != expected_prev:
                reason = (
                    "previous_hash does not match the preceding row's current_hash; "
                    "a row was deleted, inserted or reordered"
                    if index > 0
                    else (
                        "the first chained row is not genesis; rows were removed "
                        "from the start of the log"
                    )
                )
                return ChainVerification(
                    valid=False,
                    events=len(rows),
                    last_hash=expected_prev,
                    last_seq=expected_seq - 1,
                    broken_id=row_id,
                    broken_seq=seq,
                    reason=reason,
                    checked_at=checked_at,
                )
            recomputed = compute_hash(row, stored_prev, seq)
            if recomputed != row.get("current_hash"):
                return ChainVerification(
                    valid=False,
                    events=len(rows),
                    last_hash=expected_prev,
                    last_seq=expected_seq - 1,
                    broken_id=row_id,
                    broken_seq=seq,
                    reason=(
                        "row contents do not match current_hash; one or more fields "
                        "were modified after the row was written"
                    ),
                    checked_at=checked_at,
                )
            expected_prev = row["current_hash"]
            expected_seq += 1

        return ChainVerification(
            valid=True,
            events=len(rows),
            last_hash=expected_prev,
            last_seq=expected_seq - 1,
            checked_at=checked_at,
        )
    except sqlite3.DatabaseError as exc:
        return ChainVerification(
            valid=False,
            events=0,
            last_hash=GENESIS_HASH,
            last_seq=0,
            error=f"audit database is unreadable: {exc}",
            checked_at=checked_at,
        )
    finally:
        conn.close()


def verify_rows(rows: Iterable[Mapping[str, Any]]) -> ChainVerification:
    """Verify an in-memory sequence of rows. For tests and non-SQLite sinks."""
    materialised = list(rows)
    checked_at = datetime.now(timezone.utc).isoformat()
    if not materialised:
        return ChainVerification(
            valid=True, events=0, last_hash=GENESIS_HASH, last_seq=0, checked_at=checked_at
        )
    expected_prev, expected_seq = GENESIS_HASH, 1
    for index, row in enumerate(materialised):
        seq = int(row.get("chain_seq") or 0)
        stored_prev = row.get("previous_hash")
        if seq != expected_seq or stored_prev != expected_prev:
            return ChainVerification(
                valid=False,
                events=len(materialised),
                last_hash=expected_prev,
                last_seq=expected_seq - 1,
                broken_id=str(row.get("id")),
                broken_seq=seq,
                reason="chain link mismatch at this row",
                checked_at=checked_at,
            )
        if compute_hash(row, stored_prev, seq) != row.get("current_hash"):
            return ChainVerification(
                valid=False,
                events=len(materialised),
                last_hash=expected_prev,
                last_seq=expected_seq - 1,
                broken_id=str(row.get("id")),
                broken_seq=seq,
                reason="row contents do not match current_hash",
                checked_at=checked_at,
            )
        expected_prev, expected_seq = row["current_hash"], expected_seq + 1
    return ChainVerification(
        valid=True,
        events=len(materialised),
        last_hash=expected_prev,
        last_seq=expected_seq - 1,
        checked_at=checked_at,
    )


__all__ = [
    "CHAIN_COLUMNS",
    "GENESIS_HASH",
    "GENESIS_SENTENCE",
    "HASHED_FIELDS",
    "ChainState",
    "ChainVerification",
    "append_link",
    "canonical_json",
    "canonical_payload",
    "chain_columns_present",
    "chain_transaction",
    "compute_hash",
    "ensure_chain",
    "link_hash",
    "verify_chain",
    "verify_rows",
]
