"""Deterministic demo dataset access (``data/demo``).

The operations surfaces (equipment, work orders, approvals, analytics) need
records to serve before a real SAP/CMMS/historian connector is configured.
This module reads the committed, deterministic dataset in ``data/demo`` and
serves it through one narrow interface.

Honest boundaries, on purpose:

* Nothing here is fabricated at runtime. Every record comes from a file on
  disk. If the dataset is missing, every accessor raises
  :class:`DemoDataUnavailable` and the API answers ``503`` instead of
  inventing rows.
* Every payload carries ``source: "demo-dataset"`` so a caller (and the UI's
  sovereignty indicator) can never mistake it for connector-backed truth.
* Writes (create work order, decide approval) are applied to an in-process
  overlay. They are visible for the life of the process and are *not* written
  back to disk unless ``P117_DEMO_WRITEBACK=true``. A restart returns to the
  committed story.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE = "demo-dataset"


class DemoDataUnavailable(RuntimeError):
    """The demo dataset is not present. Reported, never papered over."""

    reason = "demo_data_unavailable"
    status_code = 503

    def __init__(self, path: Path, detail: str = "") -> None:
        message = f"demo dataset not available at {path}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.message = message
        self.path = path


class DemoStateError(ValueError):
    """An illegal state transition was requested."""

    reason = "invalid_transition"
    status_code = 409


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


def default_demo_dir() -> Path:
    """``P117_DEMO_DIR`` if set, else ``<repo>/data/demo``."""
    override = os.getenv("P117_DEMO_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "demo"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DemoStore:
    """Read the committed demo dataset; hold runtime mutations in memory."""

    def __init__(self, demo_dir: Path | None = None, *, writeback: bool | None = None) -> None:
        self._dir = Path(demo_dir) if demo_dir else default_demo_dir()
        if writeback is None:
            writeback = os.getenv("P117_DEMO_WRITEBACK", "").strip().lower() in {"1", "true", "yes"}
        self._writeback = bool(writeback)
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        # Runtime overlay: created rows and applied decisions.
        self._created_work_orders: list[dict[str, Any]] = []
        self._work_order_patches: dict[str, dict[str, Any]] = {}
        self._approval_patches: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------ plumbing
    @property
    def directory(self) -> Path:
        return self._dir

    def available(self) -> bool:
        return (self._dir / "equipment" / "equipment.json").is_file()

    def _read(self, relative: str) -> Any:
        path = self._dir / relative
        cached = self._cache.get(relative)
        try:
            stamp = path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise DemoDataUnavailable(path, "file missing") from exc
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DemoDataUnavailable(path, str(exc)) from exc
        self._cache[relative] = (stamp, payload)
        return payload

    def _persist(self, relative: str, payload: Any) -> None:
        if not self._writeback:
            return
        path = self._dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self._cache.pop(relative, None)

    # ----------------------------------------------------------- equipment
    def equipment(
        self,
        *,
        status: str | None = None,
        criticality: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self._read("equipment/equipment.json"))
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if criticality:
            rows = [r for r in rows if r.get("criticality") == criticality]
        if query:
            needle = query.strip().lower()
            rows = [
                r
                for r in rows
                if needle in str(r.get("id", "")).lower()
                or needle in str(r.get("name", "")).lower()
                or needle in str(r.get("unit", "")).lower()
            ]
        return rows

    def equipment_item(self, equipment_id: str) -> dict[str, Any]:
        for row in self._read("equipment/equipment.json"):
            if str(row.get("id", "")).lower() == equipment_id.lower():
                return row
        raise KeyError(equipment_id)

    def telemetry(self, equipment_id: str, *, signal: str | None = None) -> dict[str, Any]:
        series = self._read("telemetry/telemetry.json")
        rows = [s for s in series if str(s.get("equipmentId", "")).lower() == equipment_id.lower()]
        if signal:
            rows = [s for s in rows if s.get("signal") == signal]
        if not rows:
            raise KeyError(equipment_id)
        return {"equipmentId": equipment_id, "series": rows, "source": SOURCE}

    # ----------------------------------------------------------- documents
    def documents(self, *, query: str | None = None, doc_type: str | None = None) -> list[dict[str, Any]]:
        rows = list(self._read("documents/index.json"))
        if doc_type:
            rows = [r for r in rows if r.get("type") == doc_type]
        if query:
            needle = query.strip().lower()
            rows = [
                r
                for r in rows
                if needle in str(r.get("title", "")).lower()
                or needle in " ".join(r.get("tags", [])).lower()
                or needle in str(r.get("equipmentId", "")).lower()
            ]
        return rows

    def document_text(self, document_id: str) -> str:
        for row in self._read("documents/index.json"):
            if row.get("id") == document_id:
                relative = row.get("path")
                if not relative:
                    raise KeyError(document_id)
                path = self._dir / relative
                if not path.is_file():
                    raise DemoDataUnavailable(path, "document body missing")
                return path.read_text(encoding="utf-8")
        raise KeyError(document_id)

    # --------------------------------------------------------- work orders
    def work_orders(
        self, *, status: str | None = None, equipment_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self._read("work-orders.json")] + [
            dict(r) for r in self._created_work_orders
        ]
        for row in rows:
            patch = self._work_order_patches.get(str(row.get("id")))
            if patch:
                row.update(patch)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if equipment_id:
            rows = [
                r
                for r in rows
                if str(r.get("equipmentId", "")).lower() == equipment_id.lower()
            ]
        return rows

    def work_order(self, work_order_id: str) -> dict[str, Any]:
        for row in self.work_orders():
            if str(row.get("id", "")).lower() == work_order_id.lower():
                return row
        raise KeyError(work_order_id)

    def next_work_order_id(self) -> str:
        numbers = []
        for row in self.work_orders():
            raw = str(row.get("id", ""))
            tail = raw.rsplit("-", 1)[-1]
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
                raise DemoStateError(f"unknown work-order status {row['status']!r}")
            self._created_work_orders.append(row)
            if self._writeback:
                committed = list(self._read("work-orders.json")) + [row]
                self._persist("work-orders.json", committed)
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
                    raise DemoStateError(
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
            merged = dict(self._work_order_patches.get(str(current["id"]), {}))
            merged.update(patch)
            self._work_order_patches[str(current["id"])] = merged
            result = dict(current)
            result.update(merged)
            return result

    # ----------------------------------------------------------- approvals
    def approvals(self, *, status: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self._read("approvals.json")]
        for row in rows:
            patch = self._approval_patches.get(str(row.get("id")))
            if patch:
                row.update(patch)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows

    def approval(self, approval_id: str) -> dict[str, Any]:
        for row in self.approvals():
            if str(row.get("id", "")).lower() == approval_id.lower():
                return row
        raise KeyError(approval_id)

    def decide_approval(
        self, approval_id: str, *, decision: str, actor: str, note: str | None = None
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise DemoStateError(f"decision must be approved|rejected, got {decision!r}")
        with self._lock:
            current = self.approval(approval_id)
            allowed = APPROVAL_TRANSITIONS.get(str(current.get("status")), frozenset())
            if decision not in allowed:
                raise DemoStateError(
                    f"{approval_id}: already {current.get('status')!r}; cannot {decision}"
                )
            patch = {
                "status": decision,
                "decidedBy": actor,
                "decidedAt": _now(),
                "decisionNote": note or "",
            }
            self._approval_patches[str(current["id"])] = patch
            result = dict(current)
            result.update(patch)
            return result

    # ----------------------------------------------------------- analytics
    def analytics(self) -> dict[str, Any]:
        """KPIs computed from the dataset — not hand-written numbers."""
        equipment = self.equipment()
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
        trends = self._read("analytics.json")
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
            "trends": trends,
            "source": SOURCE,
            "computedAt": _now(),
        }

    # -------------------------------------------------- operational history
    def history(self, equipment_id: str | None = None) -> list[dict[str, Any]]:
        rows = list(self._read("history.json"))
        if equipment_id:
            rows = [
                r
                for r in rows
                if str(r.get("equipmentId", "")).lower() == equipment_id.lower()
            ]
        return rows


_store: DemoStore | None = None
_store_lock = threading.Lock()


def get_demo_store(demo_dir: Path | None = None) -> DemoStore:
    """Process-wide store so runtime mutations survive across requests."""
    global _store
    with _store_lock:
        if _store is None or (demo_dir is not None and Path(demo_dir) != _store.directory):
            _store = DemoStore(demo_dir)
        return _store


__all__ = [
    "APPROVAL_TRANSITIONS",
    "SOURCE",
    "WORK_ORDER_TRANSITIONS",
    "DemoDataUnavailable",
    "DemoStateError",
    "DemoStore",
    "default_demo_dir",
    "get_demo_store",
]