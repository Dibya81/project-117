"""Operational records for the console's equipment/operations surfaces.

This module replaces the synthetic ``data/demo`` reader (``backend/storage/demo.py``).
It serves the same HTTP shapes from real sources:

* **Equipment** is rehydrated from the project's real plant dataset in SQLite
  (``backend.simulation.datasets.load_plant`` → ``SimulationStore`` → the
  committed ``seed_plants.sql``). The default plant is ``refinery`` (58
  assets); ``?plant=steel`` serves the other dataset (55). Every plant asset is
  mapped onto the *existing* response fields, so the frontend keeps working and
  no second shape is invented.
* **Work orders and approvals** live in a local SQLite database
  (``P117_OPERATIONS_DB``, default ``data/operations.db``). There is no real
  committed seed for either yet, so the stores start empty and grow only from
  runtime writes: ``POST /api/work-orders`` inserts a row that survives a
  restart. Nothing here fabricates a plausible-looking record to fill a table.
* **Analytics** is computed from whatever rows exist in those two stores.

Honest boundaries, on purpose:

* A missing plant dataset raises :class:`OperationsDataUnavailable` and the API
  answers ``503`` instead of inventing assets.
* Runtime writes are committed to SQLite before the response is returned.
* Telemetry and per-asset operational history have no real backing store yet;
  they are reported as absent (``404`` / empty list) rather than synthesized.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.simulation.datasets import DatasetError, list_plants, load_plant
from backend.simulation.models import AssetState, Equipment, Plant

#: ``source`` values reported to callers. The synthetic ``demo-dataset`` label
#: is gone: equipment is the real plant definition, the rest is local SQLite.
EQUIPMENT_SOURCE = "plant-dataset"
OPERATIONS_SOURCE = "operations-sqlite"
#: Backwards-compatible alias for callers that imported the old single constant.
SOURCE = EQUIPMENT_SOURCE

#: Assumed inspection cadence used to derive ``nextInspection``. The plant model
#: records only the last inspection, so the next one is last + 90 days — stated
#: here rather than buried, so nobody mistakes it for a stored field.
INSPECTION_INTERVAL_DAYS = 90

CRITICALITY_LABELS = {1: "low", 2: "medium", 3: "high"}

#: Plant ``AssetState`` → the console's equipment status vocabulary.
STATUS_BY_STATE: dict[str, str] = {
    AssetState.NORMAL.value: "healthy",
    AssetState.WARNING.value: "warning",
    AssetState.CRITICAL.value: "critical",
    AssetState.FAILED.value: "critical",
    AssetState.DISABLED.value: "maintenance",
    AssetState.INVESTIGATING.value: "warning",
    AssetState.ACTING.value: "warning",
    AssetState.VERIFYING.value: "warning",
    AssetState.VERIFIED.value: "healthy",
}

# Work-order lifecycle. Terminal states have no outgoing edges; the API
# rejects anything not listed here rather than silently accepting it.
WORK_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"open", "cancelled"}),
    "open": frozenset({"in_progress", "on_hold", "cancelled"}),
    "in_progress": frozenset({"on_hold", "completed", "cancelled"}),
    "on_hold": frozenset({"in_progress", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

APPROVAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "rejected"}),
    "approved": frozenset(),
    "rejected": frozenset(),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_orders (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    equipment_id TEXT,
    priority    TEXT NOT NULL DEFAULT 'medium',
    status      TEXT NOT NULL DEFAULT 'draft',
    type        TEXT NOT NULL DEFAULT 'corrective',
    assignee    TEXT,
    due_date    TEXT,
    description TEXT NOT NULL DEFAULT '',
    evidence    TEXT NOT NULL DEFAULT '[]',
    created_by  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT,
    updated_by  TEXT,
    last_note   TEXT,
    origin      TEXT NOT NULL DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS approvals (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    type          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    risk          TEXT NOT NULL DEFAULT 'medium',
    requested_by  TEXT,
    requested_at  TEXT,
    required_role TEXT,
    related_id    TEXT,
    summary       TEXT NOT NULL DEFAULT '',
    evidence      TEXT NOT NULL DEFAULT '[]',
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT
);
"""


class OperationsDataUnavailable(RuntimeError):
    """The real plant dataset (or the operations database) is unusable."""

    reason = "operations_data_unavailable"
    status_code = 503

    def __init__(self, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path


class OperationsStateError(ValueError):
    """An illegal state transition was requested."""

    reason = "invalid_transition"
    status_code = 409


def default_operations_db() -> Path:
    """``P117_OPERATIONS_DB`` if set, else ``<repo>/data/operations.db``."""
    override = os.getenv("P117_OPERATIONS_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "operations.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _next_inspection(last: date | None) -> str | None:
    return (last + timedelta(days=INSPECTION_INTERVAL_DAYS)).isoformat() if last else None


class OperationsStore:
    """Real plant equipment + SQLite-backed runtime work orders and approvals."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        default_plant: str | None = None,
    ) -> None:
        self._db_path = Path(db_path) if db_path else default_operations_db()
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()
        self._default_plant = (
            default_plant or os.getenv("P117_OPERATIONS_PLANT", "").strip() or "refinery"
        )
        self._plants: dict[str, Plant] = {}
        self._equipment_by_key: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------ plumbing
    @property
    def directory(self) -> Path:
        """The SQLite file backing runtime records (kept for callers/tests)."""
        return self._db_path

    @property
    def default_plant(self) -> str:
        return self._default_plant

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ----------------------------------------------------------- equipment
    def _known_plant_ids(self) -> list[str]:
        try:
            return [str(meta["id"]) for meta in list_plants()]
        except Exception as exc:  # missing/corrupt simulation DB
            raise OperationsDataUnavailable(
                f"plant dataset unavailable: {exc}", getattr(exc, "path", None)
            ) from exc

    def _plant(self, plant_id: str | None = None) -> Plant:
        pid = plant_id or self._default_plant
        known = self._known_plant_ids()
        if pid not in known:
            raise KeyError(pid)
        if pid not in self._plants:
            try:
                self._plants[pid] = load_plant(pid)
            except DatasetError as exc:
                raise OperationsDataUnavailable(f"plant {pid} failed to load: {exc}") from exc
        return self._plants[pid]

    @staticmethod
    def _map_equipment(equipment: Equipment, areas: dict[str, str]) -> dict[str, Any]:
        area_name = areas.get(equipment.area_id, equipment.area_id)
        label = CRITICALITY_LABELS.get(int(equipment.criticality), "medium")
        installed = _parse_date(equipment.installed)
        last = _parse_date(equipment.last_inspection)
        signals = [
            {
                "signal": sensor.measurement.value,
                "value": sensor.nominal,
                "unit": sensor.unit,
                "baseline": sensor.nominal,
                "limit": sensor.normal_max,
                "deltaPercent": 0,
                "state": "normal",
            }
            for sensor in equipment.sensors
        ]
        return {
            "id": equipment.id,
            "name": equipment.name,
            "type": equipment.kind.value,
            "unit": area_name,
            "area": area_name,
            # The dataset carries a real plan coordinate for every asset, inside
            # its area rectangle. The API did not expose it, so the console
            # invented a position and every unit collapsed onto a single line.
            "x": equipment.x,
            "y": equipment.y,
            "criticality": label,
            "status": STATUS_BY_STATE.get(equipment.state.value, "healthy"),
            "manufacturer": equipment.manufacturer,
            "model": equipment.model,
            "installedYear": installed.year if installed else None,
            "lastInspection": last.isoformat() if last else None,
            "nextInspection": _next_inspection(last),
            "sopId": None,
            "manualId": None,
            "tags": [equipment.kind.value, equipment.area_id, equipment.tag],
            "keySignals": signals,
            "summary": (
                f"{equipment.name} ({equipment.tag}) is a {equipment.kind.value} "
                f"in {area_name}; criticality {label}, {len(signals)} instrumented point(s)."
            ),
        }

    def _rows_for_plant(self, plant_id: str | None) -> list[dict[str, Any]]:
        plant = self._plant(plant_id)
        areas = {area.id: area.name for area in plant.areas}
        return [self._map_equipment(equipment, areas) for equipment in plant.equipment]

    def equipment(
        self,
        *,
        plant: str | None = None,
        status: str | None = None,
        criticality: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._rows_for_plant(plant)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if criticality:
            rows = [row for row in rows if row.get("criticality") == criticality]
        if query:
            needle = query.strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("id", "")).lower()
                or needle in str(row.get("name", "")).lower()
                or needle in str(row.get("unit", "")).lower()
            ]
        return rows

    def _equipment_index(self) -> dict[str, dict[str, Any]]:
        """Every plant's equipment keyed by id and tag (ids are unique per plant)."""
        if self._equipment_by_key is not None:
            return self._equipment_by_key
        index: dict[str, dict[str, Any]] = {}
        for pid in self._known_plant_ids():
            try:
                plant = self._plant(pid)
            except OperationsDataUnavailable:
                continue
            areas = {area.id: area.name for area in plant.areas}
            for equipment in plant.equipment:
                row = self._map_equipment(equipment, areas)
                index.setdefault(equipment.id.lower(), row)
                index.setdefault(equipment.tag.lower(), row)
        self._equipment_by_key = index
        return index

    def equipment_item(self, equipment_id: str) -> dict[str, Any]:
        row = self._equipment_index().get(equipment_id.lower())
        if row is None:
            raise KeyError(equipment_id)
        return row

    def telemetry(self, equipment_id: str, *, signal: str | None = None) -> dict[str, Any]:
        """No persisted telemetry feed yet; reported absent, never synthesized."""
        self.equipment_item(equipment_id)  # 404 for an unknown tag
        raise KeyError(equipment_id)

    # ----------------------------------------------------------- documents
    def documents(self, *, query: str | None = None, doc_type: str | None = None) -> list[dict[str, Any]]:
        """Per-equipment document linkage has no real backing store yet."""
        return []

    def document_text(self, document_id: str) -> str:
        raise KeyError(document_id)

    # --------------------------------------------------------- work orders
    @staticmethod
    def _wo_row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            evidence = json.loads(row["evidence"] or "[]")
        except ValueError:
            evidence = []
        out = {
            "id": row["id"],
            "title": row["title"],
            "equipmentId": row["equipment_id"],
            "priority": row["priority"],
            "status": row["status"],
            "type": row["type"],
            "assignee": row["assignee"],
            "dueDate": row["due_date"],
            "description": row["description"],
            "evidence": evidence,
            "createdBy": row["created_by"],
            "createdAt": row["created_at"],
            "origin": row["origin"],
            "source": "runtime",
        }
        if row["updated_at"] is not None:
            out["updatedAt"] = row["updated_at"]
        if row["updated_by"] is not None:
            out["updatedBy"] = row["updated_by"]
        if row["last_note"] is not None:
            out["lastNote"] = row["last_note"]
        return out

    def work_orders(
        self, *, status: str | None = None, equipment_id: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM work_orders"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if equipment_id:
            clauses.append("lower(equipment_id)=lower(?)")
            params.append(equipment_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, id"
        with self._lock:
            rows = [self._wo_row(row) for row in self._db.execute(sql, params).fetchall()]
        return rows

    def work_order(self, work_order_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM work_orders WHERE lower(id)=lower(?)", (work_order_id,)
            ).fetchone()
        if row is None:
            raise KeyError(work_order_id)
        return self._wo_row(row)

    def next_work_order_id(self) -> str:
        with self._lock:
            rows = self._db.execute("SELECT id FROM work_orders").fetchall()
        numbers = []
        for row in rows:
            tail = str(row["id"]).rsplit("-", 1)[-1]
            if tail.isdigit():
                numbers.append(int(tail))
        return f"WO-{(max(numbers) + 1) if numbers else 9001}"

    def create_work_order(self, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
        with self._lock:
            row = {
                "id": self.next_work_order_id(),
                "title": payload["title"],
                "equipmentId": payload.get("equipmentId"),
                "priority": payload.get("priority", "medium"),
                "status": payload.get("status", "draft"),
                "type": payload.get("type", "corrective"),
                "assignee": payload.get("assignee"),
                "dueDate": payload.get("dueDate"),
                "description": payload.get("description", ""),
                "evidence": list(payload.get("evidence", [])),
                "createdBy": actor,
                "createdAt": _now(),
                "origin": payload.get("origin", "api"),
                "source": "runtime",
            }
            if row["status"] not in WORK_ORDER_TRANSITIONS:
                raise OperationsStateError(f"unknown work-order status {row['status']!r}")
            self._db.execute(
                "INSERT INTO work_orders (id,title,equipment_id,priority,status,type,assignee,"
                "due_date,description,evidence,created_by,created_at,origin)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["id"], row["title"], row["equipmentId"], row["priority"], row["status"],
                    row["type"], row["assignee"], row["dueDate"], row["description"],
                    json.dumps(row["evidence"]), row["createdBy"], row["createdAt"], row["origin"],
                ),
            )
            self._db.commit()
            return dict(row)

    def update_work_order(
        self,
        work_order_id: str,
        *,
        status: str | None = None,
        assignee: str | None = None,
        note: str | None = None,
        actor: str = "local",
    ) -> dict[str, Any]:
        with self._lock:
            current = self.work_order(work_order_id)
            patch: dict[str, Any] = {}
            if status is not None:
                allowed = WORK_ORDER_TRANSITIONS.get(str(current.get("status")), frozenset())
                if status != current.get("status") and status not in allowed:
                    raise OperationsStateError(
                        f"{work_order_id}: cannot move {current.get('status')!r} -> {status!r} "
                        f"(allowed: {sorted(allowed) or 'none, terminal state'})"
                    )
                patch["status"] = status
            if assignee is not None:
                patch["assignee"] = assignee
            if note:
                patch["lastNote"] = note
            patch["updatedAt"] = _now()
            patch["updatedBy"] = actor
            self._db.execute(
                "UPDATE work_orders SET status=?, assignee=?, last_note=?, updated_at=?,"
                " updated_by=? WHERE id=?",
                (
                    patch.get("status", current.get("status")),
                    patch.get("assignee", current.get("assignee")),
                    patch.get("lastNote", current.get("lastNote")),
                    patch["updatedAt"], patch["updatedBy"], current["id"],
                ),
            )
            self._db.commit()
            result = dict(current)
            result.update(patch)
            return result

    # ----------------------------------------------------------- approvals
    @staticmethod
    def _approval_row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            evidence = json.loads(row["evidence"] or "[]")
        except ValueError:
            evidence = []
        out = {
            "id": row["id"],
            "title": row["title"],
            "type": row["type"],
            "status": row["status"],
            "risk": row["risk"],
            "requestedBy": row["requested_by"],
            "requestedAt": row["requested_at"],
            "requiredRole": row["required_role"],
            "relatedId": row["related_id"],
            "summary": row["summary"],
            "evidence": evidence,
        }
        if row["decided_by"] is not None:
            out["decidedBy"] = row["decided_by"]
        if row["decided_at"] is not None:
            out["decidedAt"] = row["decided_at"]
        if row["decision_note"] is not None:
            out["decisionNote"] = row["decision_note"]
        return out

    def next_approval_id(self) -> str:
        """``APR-9001``-style identifier, matching the work-order convention."""
        with self._lock:
            rows = self._db.execute("SELECT id FROM approvals").fetchall()
        numbers = [int(t) for r in rows if (t := str(r["id"]).rsplit("-", 1)[-1]).isdigit()]
        return f"APR-{(max(numbers) + 1) if numbers else 9001}"

    def request_approval(
        self,
        *,
        title: str,
        approval_type: str,
        actor: str,
        summary: str = "",
        related_id: str | None = None,
        risk: str = "medium",
        required_role: str | None = None,
        evidence: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Park something for human decision. Idempotent per (type, related_id).

        Returns the existing PENDING approval when one is already open for the
        same subject. Raising a second identical request would let a queue look
        busier than the work actually is, and the operator would have to decide
        the same thing twice.

        This creates a *request*. Nothing here approves anything, and nothing
        here executes the underlying action — deciding is a separate call that
        requires ``jobs:approve``.
        """
        with self._lock:
            if related_id:
                existing = self._db.execute(
                    "SELECT * FROM approvals WHERE type=? AND related_id=? AND status='pending'",
                    (approval_type, related_id),
                ).fetchone()
                if existing is not None:
                    out = self._approval_row(existing)
                    out["deduplicated"] = True
                    return out
            approval_id = self.next_approval_id()
            self._db.execute(
                "INSERT INTO approvals (id,title,type,status,risk,requested_by,requested_at,"
                "required_role,related_id,summary,evidence) VALUES (?,?,?,'pending',?,?,?,?,?,?,?)",
                (
                    approval_id,
                    title,
                    approval_type,
                    risk,
                    actor,
                    _now(),
                    required_role,
                    related_id,
                    summary,
                    json.dumps(evidence or []),
                ),
            )
            self._db.commit()
            row = self._db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        out = self._approval_row(row)
        out["deduplicated"] = False
        return out

    def approvals(self, *, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM approvals"
        params: list[Any] = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY requested_at, id"
        with self._lock:
            return [self._approval_row(row) for row in self._db.execute(sql, params).fetchall()]

    def approval(self, approval_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM approvals WHERE lower(id)=lower(?)", (approval_id,)
            ).fetchone()
        if row is None:
            raise KeyError(approval_id)
        return self._approval_row(row)

    def decide_approval(
        self, approval_id: str, *, decision: str, actor: str, note: str | None = None
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise OperationsStateError(f"decision must be approved|rejected, got {decision!r}")
        with self._lock:
            current = self.approval(approval_id)
            allowed = APPROVAL_TRANSITIONS.get(str(current.get("status")), frozenset())
            if decision not in allowed:
                raise OperationsStateError(
                    f"{approval_id}: already {current.get('status')!r}; cannot {decision}"
                )
            decided_at = _now()
            self._db.execute(
                "UPDATE approvals SET status=?, decided_by=?, decided_at=?, decision_note=?"
                " WHERE id=?",
                (decision, actor, decided_at, note or "", current["id"]),
            )
            self._db.commit()
            result = dict(current)
            result.update(
                {
                    "status": decision,
                    "decidedBy": actor,
                    "decidedAt": decided_at,
                    "decisionNote": note or "",
                }
            )
            return result

    # ----------------------------------------------------------- analytics
    def analytics(self, *, plant: str | None = None) -> dict[str, Any]:
        """KPIs computed from the real plant definition and the runtime stores."""
        equipment = self._rows_for_plant(plant)
        work_orders = self.work_orders()
        approvals = self.approvals()
        by_status: dict[str, int] = {}
        for row in equipment:
            key = str(row.get("status", "unknown"))
            by_status[key] = by_status.get(key, 0) + 1
        wo_by_status: dict[str, int] = {}
        for row in work_orders:
            key = str(row.get("status", "unknown"))
            wo_by_status[key] = wo_by_status.get(key, 0) + 1
        return {
            "equipment": {
                "total": len(equipment),
                "byStatus": by_status,
                "critical": [r["id"] for r in equipment if r.get("status") == "critical"],
                "warning": [r["id"] for r in equipment if r.get("status") == "warning"],
            },
            "workOrders": {
                "total": len(work_orders),
                "byStatus": wo_by_status,
                "open": sum(
                    1 for r in work_orders if r.get("status") in {"open", "in_progress", "draft"}
                ),
                "highPriorityOpen": sum(
                    1
                    for r in work_orders
                    if r.get("priority") in {"high", "critical"}
                    and r.get("status") in {"open", "in_progress", "draft"}
                ),
            },
            "approvals": {
                "total": len(approvals),
                "pending": sum(1 for r in approvals if r.get("status") == "pending"),
            },
            # No real trend history is persisted yet; empty rather than invented.
            "trends": {},
            "plant": plant or self._default_plant,
            "source": OPERATIONS_SOURCE,
            "computedAt": _now(),
        }

    # -------------------------------------------------- operational history
    def history(self, equipment_id: str | None = None) -> list[dict[str, Any]]:
        """No persisted per-asset history feed yet; reported empty."""
        return []


_store: OperationsStore | None = None
_store_lock = threading.Lock()


def get_operations_store(
    db_path: str | Path | None = None, *, default_plant: str | None = None
) -> OperationsStore:
    """Process-wide store so runtime records survive across requests."""
    global _store
    with _store_lock:
        if _store is None:
            _store = OperationsStore(db_path, default_plant=default_plant)
        return _store


__all__ = [
    "APPROVAL_TRANSITIONS",
    "EQUIPMENT_SOURCE",
    "OPERATIONS_SOURCE",
    "SOURCE",
    "WORK_ORDER_TRANSITIONS",
    "OperationsDataUnavailable",
    "OperationsStateError",
    "OperationsStore",
    "default_operations_db",
    "get_operations_store",
]
