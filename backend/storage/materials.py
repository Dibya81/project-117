"""SQLite store for the industrial materials domain.

Follows the conventions already established by :mod:`backend.storage.operations`:
one file-backed SQLite database, an idempotent ``CREATE TABLE IF NOT EXISTS``
schema applied on open, a re-entrant lock around every statement, and rows mapped
to plain dicts at the boundary so the HTTP layer never sees a ``sqlite3.Row``.

Two properties this store guarantees, because the domain depends on them:

* **Movements and price observations are append-only.** There is no update and no
  delete for either. A correction is a new compensating record. An inventory or
  price history that can be silently rewritten cannot be used as evidence.
* **Every stored entity carries its provenance** as a JSON column, so a value can
  always be traced back to the source, timestamp and data status it came from.

The store does no arithmetic. ``available = quantity − reserved`` and every other
derived figure lives in :mod:`backend.materials.service`, so there is exactly one
implementation of each calculation in the system.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from backend.materials.models import (
    EquipmentMaterialRequirement,
    FinancialEvent,
    InventoryBalance,
    Material,
    MaterialMovement,
    PriceObservation,
    ProductionOutput,
    Provenance,
    Supplier,
    new_id,
    now_iso,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    material_class TEXT NOT NULL,
    unit          TEXT NOT NULL,
    location      TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'NORMAL',
    description   TEXT NOT NULL DEFAULT '',
    quality_attributes TEXT NOT NULL DEFAULT '{}',
    supplier_id   TEXT,
    cost_basis    TEXT NOT NULL DEFAULT '',
    source_process_unit TEXT,
    destination_process_unit TEXT,
    provenance    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_class ON materials(material_class);
CREATE INDEX IF NOT EXISTS idx_materials_supplier ON materials(supplier_id);

CREATE TABLE IF NOT EXISTS inventory_balances (
    id          TEXT PRIMARY KEY,
    material_id TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    quantity    REAL NOT NULL DEFAULT 0,
    reserved    REAL NOT NULL DEFAULT 0,
    unit        TEXT NOT NULL,
    threshold   REAL,
    safety_stock REAL NOT NULL DEFAULT 0,
    reorder_level REAL NOT NULL DEFAULT 0,
    timestamp   TEXT NOT NULL,
    provenance  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_balances_material ON inventory_balances(material_id, timestamp);

CREATE TABLE IF NOT EXISTS material_movements (
    id          TEXT PRIMARY KEY,
    material_id TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    quantity    REAL NOT NULL,
    unit        TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    source_location TEXT NOT NULL DEFAULT '',
    destination_location TEXT NOT NULL DEFAULT '',
    reference   TEXT NOT NULL DEFAULT '',
    provenance  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_movements_material ON material_movements(material_id, timestamp);

CREATE TABLE IF NOT EXISTS production_output (
    id          TEXT PRIMARY KEY,
    product_id  TEXT NOT NULL,
    process_unit_id TEXT NOT NULL DEFAULT '',
    quantity    REAL NOT NULL,
    unit        TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end  TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    opening     REAL,
    receipts    REAL,
    dispatches  REAL,
    adjustments REAL,
    closing     REAL,
    provenance  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_production_period ON production_output(period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_production_product ON production_output(product_id, period_start);

CREATE TABLE IF NOT EXISTS price_observations (
    id          TEXT PRIMARY KEY,
    item_id     TEXT NOT NULL,
    price       REAL NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'INR',
    unit        TEXT NOT NULL,
    observed_on TEXT NOT NULL,
    source      TEXT NOT NULL,
    data_status TEXT NOT NULL DEFAULT 'SYNTHETIC_DEMO',
    note        TEXT NOT NULL DEFAULT '',
    provenance  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prices_item ON price_observations(item_id, observed_on);

CREATE TABLE IF NOT EXISTS equipment_material_requirements (
    id           TEXT PRIMARY KEY,
    equipment_id TEXT NOT NULL,
    item_id      TEXT NOT NULL,
    quantity     REAL NOT NULL,
    unit         TEXT NOT NULL,
    schedule     TEXT NOT NULL DEFAULT '',
    purpose      TEXT NOT NULL DEFAULT '',
    failure_mode TEXT,
    provenance   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_requirements_equipment ON equipment_material_requirements(equipment_id);
CREATE INDEX IF NOT EXISTS idx_requirements_item ON equipment_material_requirements(item_id);

CREATE TABLE IF NOT EXISTS suppliers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    contact       TEXT NOT NULL DEFAULT '',
    reference     TEXT NOT NULL DEFAULT '',
    provenance    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_events (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    amount      REAL NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'INR',
    occurred_on TEXT NOT NULL,
    reference   TEXT NOT NULL DEFAULT '',
    calculation_status TEXT NOT NULL DEFAULT 'ESTIMATED',
    basis       TEXT NOT NULL DEFAULT '{}',
    provenance  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_financial_date ON financial_events(occurred_on);
"""


def default_materials_db() -> Path:
    """``P117_MATERIALS_DB`` if set, else ``<repo>/data/materials.db``."""
    override = os.getenv("P117_MATERIALS_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "materials.db"


def _loads(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def _dumps(value: Any) -> str:
    return json.dumps(value, default=str)


class MaterialsStore:
    """Materials, inventory, movements, production, prices, requirements, finance."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_materials_db()
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_SCHEMA)
            self._db.commit()

    # ------------------------------------------------------------- plumbing

    @property
    def path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return cur

    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def _one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._db.execute(sql, params).fetchone()

    def is_empty(self) -> bool:
        return int(self._one("SELECT COUNT(*) AS n FROM materials")["n"]) == 0

    def counts(self) -> dict[str, int]:
        tables = (
            "materials",
            "inventory_balances",
            "material_movements",
            "production_output",
            "price_observations",
            "equipment_material_requirements",
            "suppliers",
            "financial_events",
        )
        return {t: int(self._one(f"SELECT COUNT(*) AS n FROM {t}")["n"]) for t in tables}

    # ------------------------------------------------------------ materials

    @staticmethod
    def _material(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "material_class": row["material_class"],
            "unit": row["unit"],
            "location": row["location"],
            "status": row["status"],
            "description": row["description"],
            "quality_attributes": _loads(row["quality_attributes"], {}),
            "supplier_id": row["supplier_id"],
            "cost_basis": row["cost_basis"],
            "source_process_unit": row["source_process_unit"],
            "destination_process_unit": row["destination_process_unit"],
            "provenance": _loads(row["provenance"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def upsert_material(self, material: Material) -> dict[str, Any]:
        payload = material.model_dump(mode="json")
        self._exec(
            "INSERT INTO materials (id,name,material_class,unit,location,status,description,"
            "quality_attributes,supplier_id,cost_basis,source_process_unit,destination_process_unit,"
            "provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, material_class=excluded.material_class,"
            "unit=excluded.unit, location=excluded.location, status=excluded.status,"
            "description=excluded.description, quality_attributes=excluded.quality_attributes,"
            "supplier_id=excluded.supplier_id, cost_basis=excluded.cost_basis,"
            "source_process_unit=excluded.source_process_unit,"
            "destination_process_unit=excluded.destination_process_unit,"
            "provenance=excluded.provenance, updated_at=excluded.updated_at",
            (
                payload["id"],
                payload["name"],
                payload["material_class"],
                payload["unit"],
                payload["location"],
                payload["status"],
                payload["description"],
                _dumps(payload["quality_attributes"]),
                payload["supplier_id"],
                payload["cost_basis"],
                payload["source_process_unit"],
                payload["destination_process_unit"],
                _dumps(payload["provenance"]),
                payload["created_at"],
                payload["updated_at"],
            ),
        )
        return self.material(payload["id"])

    def material(self, material_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM materials WHERE lower(id)=lower(?)", (material_id,))
        return self._material(row) if row else None

    def materials(
        self,
        *,
        material_class: str | None = None,
        supplier_id: str | None = None,
        location: str | None = None,
        search: str | None = None,
        ids: Iterable[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "name",
    ) -> list[dict[str, Any]]:
        """Filtered, paginated materials. Never returns the whole table by default."""
        allowed_order = {"name", "id", "material_class", "updated_at"}
        order = order_by if order_by in allowed_order else "name"
        sql = "SELECT * FROM materials"
        clauses: list[str] = []
        params: list[Any] = []
        if material_class:
            clauses.append("material_class=?")
            params.append(material_class)
        if supplier_id:
            clauses.append("supplier_id=?")
            params.append(supplier_id)
        if location:
            clauses.append("lower(location)=lower(?)")
            params.append(location)
        if search:
            clauses.append("(lower(name) LIKE ? OR lower(id) LIKE ? OR lower(description) LIKE ?)")
            needle = f"%{search.lower()}%"
            params.extend([needle, needle, needle])
        if ids is not None:
            wanted = [i for i in ids]
            if not wanted:
                return []
            clauses.append(f"id IN ({','.join('?' * len(wanted))})")
            params.extend(wanted)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 500)), max(0, offset)])
        return [self._material(r) for r in self._rows(sql, tuple(params))]

    def count_materials(
        self,
        *,
        material_class: str | None = None,
        search: str | None = None,
    ) -> int:
        sql = "SELECT COUNT(*) AS n FROM materials"
        clauses: list[str] = []
        params: list[Any] = []
        if material_class:
            clauses.append("material_class=?")
            params.append(material_class)
        if search:
            clauses.append("(lower(name) LIKE ? OR lower(id) LIKE ?)")
            needle = f"%{search.lower()}%"
            params.extend([needle, needle])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return int(self._one(sql, tuple(params))["n"])

    # ------------------------------------------------------------ inventory

    @staticmethod
    def _balance(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "material_id": row["material_id"],
            "location": row["location"],
            "quantity": row["quantity"],
            "reserved": row["reserved"],
            "unit": row["unit"],
            "threshold": row["threshold"],
            "safety_stock": row["safety_stock"],
            "reorder_level": row["reorder_level"],
            "timestamp": row["timestamp"],
            "provenance": _loads(row["provenance"], {}),
        }

    def add_balance(self, balance: InventoryBalance) -> dict[str, Any]:
        p = balance.model_dump(mode="json")
        self._exec(
            "INSERT INTO inventory_balances (id,material_id,location,quantity,reserved,unit,threshold,"
            "safety_stock,reorder_level,timestamp,provenance) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                p["material_id"],
                p["location"],
                p["quantity"],
                p["reserved"],
                p["unit"],
                p["threshold"],
                p["safety_stock"],
                p["reorder_level"],
                p["timestamp"],
                _dumps(p["provenance"]),
            ),
        )
        return self._balance(self._one("SELECT * FROM inventory_balances WHERE id=?", (p["id"],)))

    def balances(self, material_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM inventory_balances WHERE lower(material_id)=lower(?) "
            "ORDER BY timestamp DESC, id LIMIT ?",
            (material_id, max(1, min(limit, 500))),
        )
        return [self._balance(r) for r in rows]

    def latest_balance(
        self, material_id: str, *, location: str | None = None
    ) -> dict[str, Any] | None:
        """The newest balance row for a material — the current position."""
        if location:
            row = self._one(
                "SELECT * FROM inventory_balances WHERE lower(material_id)=lower(?) "
                "AND lower(location)=lower(?) ORDER BY timestamp DESC, id DESC LIMIT 1",
                (material_id, location),
            )
        else:
            row = self._one(
                "SELECT * FROM inventory_balances WHERE lower(material_id)=lower(?) "
                "ORDER BY timestamp DESC, id DESC LIMIT 1",
                (material_id,),
            )
        return self._balance(row) if row else None

    def all_balances(self, *, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM inventory_balances ORDER BY timestamp DESC, id LIMIT ?",
            (max(1, min(limit, 2000)),),
        )
        return [self._balance(r) for r in rows]

    # ------------------------------------------------------------ movements

    @staticmethod
    def _movement(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "material_id": row["material_id"],
            "movement_type": row["movement_type"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "timestamp": row["timestamp"],
            "source_location": row["source_location"],
            "destination_location": row["destination_location"],
            "reference": row["reference"],
            "provenance": _loads(row["provenance"], {}),
        }

    def append_movement(self, movement: MaterialMovement) -> dict[str, Any]:
        """Append-only. There is deliberately no update or delete counterpart."""
        p = movement.model_dump(mode="json")
        self._exec(
            "INSERT INTO material_movements (id,material_id,movement_type,quantity,unit,timestamp,"
            "source_location,destination_location,reference,provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                p["material_id"],
                p["movement_type"],
                p["quantity"],
                p["unit"],
                p["timestamp"],
                p["source_location"],
                p["destination_location"],
                p["reference"],
                _dumps(p["provenance"]),
            ),
        )
        return self._movement(self._one("SELECT * FROM material_movements WHERE id=?", (p["id"],)))

    def movements(
        self,
        material_id: str | None = None,
        *,
        movement_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM material_movements"
        clauses: list[str] = []
        params: list[Any] = []
        if material_id:
            clauses.append("lower(material_id)=lower(?)")
            params.append(material_id)
        if movement_type:
            clauses.append("movement_type=?")
            params.append(movement_type)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 1000)), max(0, offset)])
        return [self._movement(r) for r in self._rows(sql, tuple(params))]

    # ----------------------------------------------------------- production

    @staticmethod
    def _production(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "product_id": row["product_id"],
            "process_unit_id": row["process_unit_id"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "period_type": row["period_type"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "source": row["source"],
            "opening": row["opening"],
            "receipts": row["receipts"],
            "dispatches": row["dispatches"],
            "adjustments": row["adjustments"],
            "closing": row["closing"],
            "provenance": _loads(row["provenance"], {}),
        }

    def add_production(self, output: ProductionOutput) -> dict[str, Any]:
        p = output.model_dump(mode="json")
        self._exec(
            "INSERT INTO production_output (id,product_id,process_unit_id,quantity,unit,period_type,"
            "period_start,period_end,source,opening,receipts,dispatches,adjustments,closing,provenance) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                p["product_id"],
                p["process_unit_id"],
                p["quantity"],
                p["unit"],
                p["period_type"],
                p["period_start"],
                p["period_end"],
                p["source"],
                p["opening"],
                p["receipts"],
                p["dispatches"],
                p["adjustments"],
                p["closing"],
                _dumps(p["provenance"]),
            ),
        )
        return self._production(self._one("SELECT * FROM production_output WHERE id=?", (p["id"],)))

    def production(
        self,
        *,
        product_id: str | None = None,
        process_unit_id: str | None = None,
        period_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM production_output"
        clauses: list[str] = []
        params: list[Any] = []
        for col, val in (
            ("product_id", product_id),
            ("process_unit_id", process_unit_id),
            ("period_type", period_type),
        ):
            if val:
                clauses.append(f"lower({col})=lower(?)")
                params.append(val)
        if since:
            clauses.append("period_start >= ?")
            params.append(since)
        if until:
            clauses.append("period_end <= ?")
            params.append(until)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY period_start DESC, id LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 2000)), max(0, offset)])
        return [self._production(r) for r in self._rows(sql, tuple(params))]

    # --------------------------------------------------------------- prices

    @staticmethod
    def _price(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "item_id": row["item_id"],
            "price": row["price"],
            "currency": row["currency"],
            "unit": row["unit"],
            "observed_on": row["observed_on"],
            "source": row["source"],
            "data_status": row["data_status"],
            "note": row["note"],
            "provenance": _loads(row["provenance"], {}),
        }

    def append_price(self, observation: PriceObservation) -> dict[str, Any]:
        """Append-only: a new observation never replaces an earlier one."""
        p = observation.model_dump(mode="json")
        self._exec(
            "INSERT INTO price_observations (id,item_id,price,currency,unit,observed_on,source,"
            "data_status,note,provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                p["item_id"],
                p["price"],
                p["currency"],
                p["unit"],
                p["observed_on"],
                p["source"],
                p["data_status"],
                p["note"],
                _dumps(p["provenance"]),
            ),
        )
        return self._price(self._one("SELECT * FROM price_observations WHERE id=?", (p["id"],)))

    def prices(
        self,
        item_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        limit: int = 400,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM price_observations WHERE lower(item_id)=lower(?)"
        params: list[Any] = [item_id]
        if since:
            sql += " AND observed_on >= ?"
            params.append(since)
        if until:
            sql += " AND observed_on <= ?"
            params.append(until)
        sql += " ORDER BY observed_on DESC, id DESC LIMIT ?"
        params.append(max(1, min(limit, 2000)))
        return [self._price(r) for r in self._rows(sql, tuple(params))]

    def latest_price(self, item_id: str, *, before: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM price_observations WHERE lower(item_id)=lower(?)"
        params: list[Any] = [item_id]
        if before:
            sql += " AND observed_on <= ?"
            params.append(before)
        sql += " ORDER BY observed_on DESC, id DESC LIMIT 1"
        row = self._one(sql, tuple(params))
        return self._price(row) if row else None

    # --------------------------------------------------------- requirements

    @staticmethod
    def _requirement(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "equipment_id": row["equipment_id"],
            "item_id": row["item_id"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "schedule": row["schedule"],
            "purpose": row["purpose"],
            "failure_mode": row["failure_mode"],
            "provenance": _loads(row["provenance"], {}),
        }

    def upsert_requirement(self, requirement: EquipmentMaterialRequirement) -> dict[str, Any]:
        p = requirement.model_dump(mode="json")
        self._exec(
            "INSERT INTO equipment_material_requirements (id,equipment_id,item_id,quantity,unit,schedule,"
            "purpose,failure_mode,provenance) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET equipment_id=excluded.equipment_id, item_id=excluded.item_id,"
            "quantity=excluded.quantity, unit=excluded.unit, schedule=excluded.schedule,"
            "purpose=excluded.purpose, failure_mode=excluded.failure_mode, provenance=excluded.provenance",
            (
                p["id"],
                p["equipment_id"],
                p["item_id"],
                p["quantity"],
                p["unit"],
                p["schedule"],
                p["purpose"],
                p["failure_mode"],
                _dumps(p["provenance"]),
            ),
        )
        return self._requirement(
            self._one("SELECT * FROM equipment_material_requirements WHERE id=?", (p["id"],))
        )

    def requirements(
        self,
        *,
        equipment_id: str | None = None,
        item_id: str | None = None,
        failure_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM equipment_material_requirements"
        clauses: list[str] = []
        params: list[Any] = []
        if equipment_id:
            clauses.append("lower(equipment_id)=lower(?)")
            params.append(equipment_id)
        if item_id:
            clauses.append("lower(item_id)=lower(?)")
            params.append(item_id)
        if failure_mode:
            clauses.append("failure_mode=?")
            params.append(failure_mode)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY equipment_id, item_id"
        return [self._requirement(r) for r in self._rows(sql, tuple(params))]

    # ------------------------------------------------------------ suppliers

    @staticmethod
    def _supplier(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "lead_time_days": row["lead_time_days"],
            "status": row["status"],
            "contact": row["contact"],
            "reference": row["reference"],
            "provenance": _loads(row["provenance"], {}),
        }

    def upsert_supplier(self, supplier: Supplier) -> dict[str, Any]:
        p = supplier.model_dump(mode="json")
        self._exec(
            "INSERT INTO suppliers (id,name,lead_time_days,status,contact,reference,provenance) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
            "lead_time_days=excluded.lead_time_days, status=excluded.status, contact=excluded.contact,"
            "reference=excluded.reference, provenance=excluded.provenance",
            (
                p["id"],
                p["name"],
                p["lead_time_days"],
                p["status"],
                p["contact"],
                p["reference"],
                _dumps(p["provenance"]),
            ),
        )
        return self.supplier(p["id"])

    def supplier(self, supplier_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM suppliers WHERE lower(id)=lower(?)", (supplier_id,))
        return self._supplier(row) if row else None

    def suppliers(self, *, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM suppliers"
        params: list[Any] = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY name"
        return [self._supplier(r) for r in self._rows(sql, tuple(params))]

    # ------------------------------------------------------------- finance

    @staticmethod
    def _financial(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "amount": row["amount"],
            "currency": row["currency"],
            "occurred_on": row["occurred_on"],
            "reference": row["reference"],
            "calculation_status": row["calculation_status"],
            "basis": _loads(row["basis"], {}),
            "provenance": _loads(row["provenance"], {}),
        }

    def add_financial_event(self, event: FinancialEvent) -> dict[str, Any]:
        p = event.model_dump(mode="json")
        self._exec(
            "INSERT INTO financial_events (id,event_type,amount,currency,occurred_on,reference,"
            "calculation_status,basis,provenance) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                p["event_type"],
                p["amount"],
                p["currency"],
                p["occurred_on"],
                p["reference"],
                p["calculation_status"],
                _dumps(p["basis"]),
                _dumps(p["provenance"]),
            ),
        )
        return self._financial(self._one("SELECT * FROM financial_events WHERE id=?", (p["id"],)))

    def financial_events(
        self,
        *,
        event_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        reference: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM financial_events"
        clauses: list[str] = []
        params: list[Any] = []
        if event_type:
            clauses.append("event_type=?")
            params.append(event_type)
        if reference:
            clauses.append("reference=?")
            params.append(reference)
        if since:
            clauses.append("occurred_on >= ?")
            params.append(since)
        if until:
            clauses.append("occurred_on <= ?")
            params.append(until)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY occurred_on DESC, id DESC LIMIT ?"
        params.append(max(1, min(limit, 2000)))
        return [self._financial(r) for r in self._rows(sql, tuple(params))]

    # ---------------------------------------------------------------- seed

    def clear(self) -> None:
        """Remove every row. Used by tests and by an explicit re-seed."""
        for table in (
            "financial_events",
            "equipment_material_requirements",
            "price_observations",
            "production_output",
            "material_movements",
            "inventory_balances",
            "materials",
            "suppliers",
        ):
            self._exec(f"DELETE FROM {table}")


def _api_safe(model: Any) -> dict[str, Any]:
    """Model → JSON-ready dict. Kept for callers that hold model instances."""
    return model.model_dump(mode="json")


__all__ = ["MaterialsStore", "default_materials_db", "new_id", "now_iso", "Provenance"]
