"""Durable persistence for the simulation domain.

Why this module exists: before it, incidents, agent executions, evidence,
approvals, actions, verification results, artifacts and audit records lived
only in ``PlantRuntime`` dictionaries. A backend restart erased the entire
execution history, and ``audit.recorded`` was an SSE frame with no row behind
it. The red-team audit graded that FAIL.

Design notes
------------
* **stdlib ``sqlite3`` only.** Project 117's SQLAlchemy layer
  (``backend/database``) owns documents/jobs/tool executions and needs the
  async engine; the simulation writes on the synchronous tick path, inside the
  event loop thread, and must never block on a session. A single-file SQLite
  database with WAL is the right shape here and keeps the simulation package
  dependency-free, which is also what makes it testable without network access.
  The file lives at ``P117_SIMULATION_DB`` (default ``data/simulation.db``) and
  is readable by the same tooling as the rest of the project.
* **Write-through, not write-behind.** Every state transition is committed
  before the corresponding SSE frame is published, so the stream can never
  describe something the database does not contain.
* Foreign keys are enforced (``PRAGMA foreign_keys=ON``) and every lookup path
  used by the API has an index.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(os.environ.get("P117_SIMULATION_DB", "data/simulation.db"))

#: Readings kept per plant. Nothing serves this table yet, so the window is for
#: post-hoc debugging; its purpose is to bound the file rather than to answer a
#: query. 418 sensors write ~418 rows per persisted tick, so 50k rows is roughly
#: 120 ticks of history.
TELEMETRY_RETAINED_ROWS = int(os.environ.get("P117_TELEMETRY_RETAINED_ROWS", "50000"))

#: Prune once every N persisted telemetry batches. Retention that ran on every
#: insert would cost more than the insert.
_TELEMETRY_PRUNE_EVERY = int(os.environ.get("P117_TELEMETRY_PRUNE_EVERY", "50"))

#: Committed, generated SQL that installs the dataset plants (refinery, steel)
#: and their scenarios. This is the source of truth now that the JSON datasets
#: are gone; see ``scripts/export_plant_sql.py``.
SEED_SQL = (
    Path(__file__).resolve().parents[2] / "project-117-simulation" / "database" / "seed_plants.sql"
)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS plants (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    industry    TEXT NOT NULL,
    origin      TEXT NOT NULL DEFAULT 'dataset',   -- dataset | builder
    definition  TEXT NOT NULL,                     -- full plant JSON
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
    id       TEXT NOT NULL,
    plant_id TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    x REAL, y REAL, w REAL, h REAL,
    PRIMARY KEY (plant_id, id)
);
CREATE INDEX IF NOT EXISTS ix_zones_plant ON zones(plant_id);

CREATE TABLE IF NOT EXISTS equipment (
    id           TEXT NOT NULL,
    plant_id     TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    zone_id      TEXT,
    tag          TEXT NOT NULL,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    criticality  INTEGER NOT NULL DEFAULT 2,
    manufacturer TEXT, model TEXT, installed TEXT, last_inspection TEXT,
    x REAL, y REAL,
    PRIMARY KEY (plant_id, id),
    FOREIGN KEY (plant_id, zone_id) REFERENCES zones(plant_id, id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_equipment_plant ON equipment(plant_id);
CREATE INDEX IF NOT EXISTS ix_equipment_zone  ON equipment(plant_id, zone_id);
CREATE INDEX IF NOT EXISTS ix_equipment_tag   ON equipment(tag);

CREATE TABLE IF NOT EXISTS sensors (
    id           TEXT NOT NULL,
    plant_id     TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    equipment_id TEXT NOT NULL,
    tag          TEXT NOT NULL,
    measurement  TEXT NOT NULL,
    unit         TEXT NOT NULL,
    nominal      REAL NOT NULL,
    normal_min REAL, normal_max REAL,
    warning_min REAL, warning_max REAL,
    critical_min REAL, critical_max REAL,
    is_detector  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (plant_id, id),
    FOREIGN KEY (plant_id, equipment_id) REFERENCES equipment(plant_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sensors_equipment ON sensors(plant_id, equipment_id);
CREATE INDEX IF NOT EXISTS ix_sensors_tag ON sensors(tag);

-- Actuators are the controllable points (valve position, motor speed, …).
CREATE TABLE IF NOT EXISTS actuators (
    id           TEXT NOT NULL,
    plant_id     TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    equipment_id TEXT NOT NULL,
    tag          TEXT NOT NULL,
    kind         TEXT NOT NULL,          -- position | speed | on_off
    unit         TEXT,
    PRIMARY KEY (plant_id, id),
    FOREIGN KEY (plant_id, equipment_id) REFERENCES equipment(plant_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_actuators_equipment ON actuators(plant_id, equipment_id);

CREATE TABLE IF NOT EXISTS connections (
    id       TEXT NOT NULL,
    plant_id TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    kind     TEXT NOT NULL,
    source   TEXT NOT NULL,
    target   TEXT NOT NULL,
    medium   TEXT,
    capacity REAL,
    PRIMARY KEY (plant_id, id)
);
CREATE INDEX IF NOT EXISTS ix_connections_source ON connections(plant_id, source);
CREATE INDEX IF NOT EXISTS ix_connections_target ON connections(plant_id, target);

-- Scenarios are not part of the Plant model (they drive a demo, not the
-- topology), so they get their own table keyed by (plant_id, id). The full
-- scenario JSON is kept here; callers rehydrate it, exactly like plants.
CREATE TABLE IF NOT EXISTS scenarios (
    plant_id   TEXT NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    id         TEXT NOT NULL,
    definition TEXT NOT NULL,                     -- full scenario JSON
    updated_at REAL NOT NULL,
    PRIMARY KEY (plant_id, id)
);

CREATE TABLE IF NOT EXISTS telemetry (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id  TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    value     REAL NOT NULL,
    quality   TEXT NOT NULL,
    sim_t     REAL NOT NULL,
    wall_ts   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_telemetry_sensor ON telemetry(plant_id, sensor_id, sim_t);
CREATE INDEX IF NOT EXISTS ix_telemetry_t ON telemetry(plant_id, sim_t);

CREATE TABLE IF NOT EXISTS fault_events (
    id           TEXT PRIMARY KEY,
    plant_id     TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    sensor_id    TEXT,
    mode_id      TEXT NOT NULL,
    mechanism    TEXT NOT NULL,
    detail       TEXT,
    sim_t        REAL NOT NULL,
    wall_ts      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fault_plant ON fault_events(plant_id, sim_t);

CREATE TABLE IF NOT EXISTS incidents (
    id               TEXT PRIMARY KEY,
    plant_id         TEXT NOT NULL,
    title            TEXT NOT NULL,
    severity         TEXT NOT NULL,
    status           TEXT NOT NULL,
    origin_equipment TEXT NOT NULL,
    origin_sensor    TEXT,
    failure_mode     TEXT,
    affected         TEXT NOT NULL DEFAULT '[]',
    fault_event_id   TEXT REFERENCES fault_events(id),
    created_at       REAL NOT NULL,
    resolved_at      REAL,
    wall_created     REAL NOT NULL,
    wall_updated     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_incidents_plant  ON incidents(plant_id, wall_created);
CREATE INDEX IF NOT EXISTS ix_incidents_status ON incidents(status);

-- One row per orchestrator run over an incident.
CREATE TABLE IF NOT EXISTS agent_executions (
    id           TEXT PRIMARY KEY,
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    plant_id     TEXT NOT NULL,
    orchestrator TEXT NOT NULL,
    runtime      TEXT NOT NULL,          -- which agent runtime served the run
    status       TEXT NOT NULL,
    task_count   INTEGER NOT NULL DEFAULT 0,
    started_at   REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS ix_exec_incident ON agent_executions(incident_id);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id           TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    agent        TEXT NOT NULL,
    title        TEXT NOT NULL,
    status       TEXT NOT NULL,
    sequence     INTEGER NOT NULL,
    depends_on   TEXT NOT NULL DEFAULT '[]',
    tools        TEXT NOT NULL DEFAULT '[]',
    result       TEXT,
    started_at   REAL,
    completed_at REAL,
    wall_ts      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tasks_incident ON agent_tasks(incident_id, sequence);
CREATE INDEX IF NOT EXISTS ix_tasks_agent    ON agent_tasks(agent);

CREATE TABLE IF NOT EXISTS agent_evidence (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,           -- telemetry|topology|maintenance|documents|policy
    source_id   TEXT NOT NULL,
    description TEXT NOT NULL,
    confidence  REAL NOT NULL,
    citation    TEXT,                    -- document/chunk reference when source_type=documents
    wall_ts     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evidence_task     ON agent_evidence(task_id);
CREATE INDEX IF NOT EXISTS ix_evidence_incident ON agent_evidence(incident_id);
CREATE INDEX IF NOT EXISTS ix_evidence_source   ON agent_evidence(source_type, source_id);

CREATE TABLE IF NOT EXISTS approvals (
    id           TEXT PRIMARY KEY,
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    requested_by TEXT NOT NULL,
    reason       TEXT NOT NULL,
    plan         TEXT NOT NULL,
    status       TEXT NOT NULL,          -- requested | granted | rejected
    decided_by   TEXT,
    requested_at REAL NOT NULL,
    decided_at   REAL
);
CREATE INDEX IF NOT EXISTS ix_approvals_incident ON approvals(incident_id);

CREATE TABLE IF NOT EXISTS actions (
    id           TEXT PRIMARY KEY,
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    approval_id  TEXT REFERENCES approvals(id),
    kind         TEXT NOT NULL,
    target       TEXT NOT NULL,
    executor     TEXT NOT NULL,          -- plant_actuator | sandbox
    policy       TEXT NOT NULL,          -- allowed | blocked
    policy_reason TEXT,
    status       TEXT NOT NULL,          -- started | completed | blocked | failed
    result       TEXT,
    started_at   REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS ix_actions_incident ON actions(incident_id);

CREATE TABLE IF NOT EXISTS verification_results (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    action_id   TEXT REFERENCES actions(id),
    passed      INTEGER NOT NULL,
    findings    TEXT NOT NULL,
    checks_run  INTEGER NOT NULL DEFAULT 0,
    sim_t       REAL NOT NULL,
    wall_ts     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_verification_incident ON verification_results(incident_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    filename    TEXT NOT NULL,
    verified    INTEGER NOT NULL DEFAULT 0,
    sources     INTEGER NOT NULL DEFAULT 0,
    body        TEXT,
    created_at  REAL NOT NULL,
    wall_ts     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_artifacts_incident ON artifacts(incident_id);

CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wall_ts     REAL NOT NULL,
    sim_t       REAL,
    plant_id    TEXT,
    incident_id TEXT,
    actor       TEXT NOT NULL,           -- operator | orchestrator | <agent>
    event_type  TEXT NOT NULL,
    task_id     TEXT,
    action      TEXT,
    target      TEXT,
    result      TEXT,
    approval_id TEXT,
    verification_id TEXT,
    evidence_count INTEGER DEFAULT 0,
    runtime     TEXT,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_incident ON audit_events(incident_id, wall_ts);
CREATE INDEX IF NOT EXISTS ix_audit_type     ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS ix_audit_plant    ON audit_events(plant_id, wall_ts);
"""


class SimulationStore:
    """Synchronous, thread-safe SQLite store for the simulation domain."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_DB
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # Telemetry write counter per plant, used to schedule retention without
        # running a DELETE on every tick.
        self._telemetry_writes: dict[str, int] = {}
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()
        self._seed_if_empty()

    # ------------------------------------------------------------- plumbing

    def _seed_if_empty(self) -> None:
        """Install the committed dataset seed exactly once.

        A fresh clone has an empty ``plants`` table and no dataset JSON, so the
        committed SQL seed (``project-117-simulation/database/seed_plants.sql``)
        is what gives it refinery + steel. The empty-table guard is the safety
        property: re-opening a populated database never re-applies the seed, so
        a builder plant or an operator's saved plant is never overwritten. The
        seed itself uses ``INSERT OR IGNORE``, so even a manual re-run is
        harmless.
        """
        if self.count("plants") > 0 or not SEED_SQL.exists():
            return
        with self._lock:
            self._db.executescript(SEED_SQL.read_text())
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, params).fetchall()]

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) AS n FROM {table}" + (f" WHERE {where}" if where else "")
        return int(self.query(sql, params)[0]["n"])

    # ------------------------------------------------------------- plant IO

    def save_plant(self, plant: Any, origin: str = "dataset") -> None:
        """Upsert the full plant graph: plant, zones, equipment, sensors,
        actuators, connections. Called on registration so that every foreign
        key an incident needs already resolves."""
        now = time.time()
        d = plant.model_dump() if hasattr(plant, "model_dump") else dict(plant)
        with self._lock:
            db = self._db
            db.execute(
                "INSERT INTO plants (id,name,industry,origin,definition,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name, industry=excluded.industry,"
                " origin=excluded.origin, updated_at=excluded.updated_at,"
                # A dataset plant's definition is the seeded, canonical one. The
                # engine mutates the in-memory Plant (flow, leaking, capacity…),
                # so re-registering it must not write that runtime state back
                # over the seed. Builder plants keep updating freely.
                " definition=CASE WHEN plants.origin='dataset' THEN plants.definition"
                " ELSE excluded.definition END",
                (d["id"], d["name"], d.get("industry", ""), origin, json.dumps(d), now, now),
            )
            for a in d.get("areas", []):
                db.execute(
                    "INSERT INTO zones (id,plant_id,name,x,y,w,h) VALUES (?,?,?,?,?,?,?)"
                    " ON CONFLICT(plant_id,id) DO UPDATE SET name=excluded.name",
                    (a["id"], d["id"], a["name"], a.get("x"), a.get("y"), a.get("w"), a.get("h")),
                )
            for e in d.get("equipment", []):
                db.execute(
                    "INSERT INTO equipment (id,plant_id,zone_id,tag,name,kind,criticality,"
                    "manufacturer,model,installed,last_inspection,x,y) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(plant_id,id) DO UPDATE SET tag=excluded.tag, name=excluded.name,"
                    " kind=excluded.kind, zone_id=excluded.zone_id, x=excluded.x, y=excluded.y",
                    (
                        e["id"],
                        d["id"],
                        e.get("area_id"),
                        e["tag"],
                        e["name"],
                        e["kind"],
                        e.get("criticality", 2),
                        e.get("manufacturer"),
                        e.get("model"),
                        e.get("installed"),
                        e.get("last_inspection"),
                        e.get("x"),
                        e.get("y"),
                    ),
                )
                for s in e.get("sensors", []):
                    db.execute(
                        "INSERT INTO sensors (id,plant_id,equipment_id,tag,measurement,unit,nominal,"
                        "normal_min,normal_max,warning_min,warning_max,critical_min,critical_max,is_detector)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                        " ON CONFLICT(plant_id,id) DO UPDATE SET tag=excluded.tag, nominal=excluded.nominal",
                        (
                            s["id"],
                            d["id"],
                            e["id"],
                            s["tag"],
                            s["measurement"],
                            s["unit"],
                            s["nominal"],
                            s.get("normal_min"),
                            s.get("normal_max"),
                            s.get("warning_min"),
                            s.get("warning_max"),
                            s.get("critical_min"),
                            s.get("critical_max"),
                            1 if s.get("is_detector") else 0,
                        ),
                    )
                # Controllable points are derived from equipment kind: every
                # valve has a position actuator, every rotating machine a speed
                # actuator. This mirrors what execute_plan can actually drive.
                kind = e["kind"]
                if kind in ("valve",):
                    db.execute(
                        "INSERT OR REPLACE INTO actuators (id,plant_id,equipment_id,tag,kind,unit)"
                        " VALUES (?,?,?,?,?,?)",
                        (f"a-{e['id']}-pos", d["id"], e["id"], f"{e['tag']}-ZC", "position", "%"),
                    )
                elif kind in ("pump", "compressor", "motor", "conveyor"):
                    db.execute(
                        "INSERT OR REPLACE INTO actuators (id,plant_id,equipment_id,tag,kind,unit)"
                        " VALUES (?,?,?,?,?,?)",
                        (f"a-{e['id']}-spd", d["id"], e["id"], f"{e['tag']}-SC", "speed", "%"),
                    )
            for c in d.get("connections", []):
                db.execute(
                    "INSERT INTO connections (id,plant_id,kind,source,target,medium,capacity)"
                    " VALUES (?,?,?,?,?,?,?)"
                    " ON CONFLICT(plant_id,id) DO UPDATE SET source=excluded.source, target=excluded.target",
                    (
                        c["id"],
                        d["id"],
                        c["kind"],
                        c["source"],
                        c["target"],
                        c.get("medium"),
                        c.get("capacity"),
                    ),
                )
            db.commit()

    def load_plant_definition(self, plant_id: str) -> Any | None:
        """Rehydrate a saved plant as a ``Plant`` model, or None if unknown.

        Validating through the model is deliberate: a builder plant that would
        not survive a round-trip fails here, at load, rather than half-way
        through a simulation.
        """
        rows = self.query("SELECT definition FROM plants WHERE id=?", (plant_id,))
        if not rows:
            return None
        from backend.simulation.models import Plant  # local import: avoids a cycle

        return Plant.model_validate(json.loads(rows[0]["definition"]))

    def load_plant_dict(self, plant_id: str) -> dict | None:
        rows = self.query("SELECT definition FROM plants WHERE id=?", (plant_id,))
        return json.loads(rows[0]["definition"]) if rows else None

    def plant_origin(self, plant_id: str) -> str | None:
        """Where this plant came from: 'dataset' or 'builder'.

        The origin decides whether a re-registration may overwrite the stored
        definition (dataset plants are protected from runtime write-back), so it
        must survive a reset — otherwise a Builder plant becomes a "dataset"
        plant and its next save is silently discarded.
        """
        rows = self.query("SELECT origin FROM plants WHERE id=?", (plant_id,))
        return rows[0]["origin"] if rows else None

    def list_saved_plants(self, origin: str | None = None) -> list[dict]:
        if origin:
            return self.query(
                "SELECT id,name,industry,origin,updated_at FROM plants WHERE origin=? ORDER BY updated_at DESC",
                (origin,),
            )
        return self.query(
            "SELECT id,name,industry,origin,updated_at FROM plants ORDER BY updated_at DESC"
        )

    def delete_plant(self, plant_id: str) -> bool:
        """Delete a plant and, via ON DELETE CASCADE, its graph rows."""
        cur = self._exec("DELETE FROM plants WHERE id=?", (plant_id,))
        return bool(cur.rowcount)

    def save_scenarios(self, plant_id: str, scenarios: list[Any]) -> int:
        """Upsert a plant's scenarios. Returns rows written.

        Scenarios are stored as their JSON definition (not normalised into
        columns) because they are demo scripts, not topology: the shape can
        grow without a migration, matching how ``plants.definition`` works.
        """
        rows = []
        now = time.time()
        for s in scenarios:
            d = s.model_dump() if hasattr(s, "model_dump") else dict(s)
            rows.append((plant_id, d["id"], json.dumps(d), now))
        if not rows:
            return 0
        with self._lock:
            self._db.executemany(
                "INSERT INTO scenarios (plant_id,id,definition,updated_at) VALUES (?,?,?,?)"
                " ON CONFLICT(plant_id,id) DO UPDATE SET definition=excluded.definition,"
                " updated_at=excluded.updated_at",
                rows,
            )
            self._db.commit()
        return len(rows)

    def load_scenarios(self, plant_id: str) -> list[dict]:
        """Raw scenario dicts for a plant, ordered by id. Empty when unknown."""
        return [
            json.loads(r["definition"])
            for r in self.query(
                "SELECT definition FROM scenarios WHERE plant_id=? ORDER BY id", (plant_id,)
            )
        ]

    # ------------------------------------------------------------ telemetry

    def record_telemetry(self, plant_id: str, readings: list[dict], sim_t: float) -> int:
        """Persist a tick's readings. Returns rows written.

        Retention runs from here because this is the only writer. It used to be
        an unbounded sink: ``prune_telemetry`` existed but no caller, and
        nothing reads the table, so it had grown to 742k rows (~95 MB) with no
        way to stop. Pruning on a write counter rather than on every insert
        keeps the common path cheap — a DELETE with a subquery per tick would
        cost more than the insert it follows.
        """
        now = time.time()
        rows = [
            (plant_id, r["sensor_id"], float(r["value"]), str(r["quality"]), sim_t, now)
            for r in readings
        ]
        if not rows:
            return 0
        with self._lock:
            self._db.executemany(
                "INSERT INTO telemetry (plant_id,sensor_id,value,quality,sim_t,wall_ts) VALUES (?,?,?,?,?,?)",
                rows,
            )
            self._db.commit()
            self._telemetry_writes[plant_id] = self._telemetry_writes.get(plant_id, 0) + 1
            should_prune = self._telemetry_writes[plant_id] % _TELEMETRY_PRUNE_EVERY == 0
        if should_prune:
            self.prune_telemetry(plant_id)
        return len(rows)

    def prune_telemetry(self, plant_id: str, keep: int = TELEMETRY_RETAINED_ROWS) -> int:
        """Drop all but the most recent ``keep`` readings for a plant.

        Nothing serves this table yet, so the retained window is for debugging
        rather than for an API; it exists so the file cannot grow without bound
        while the engine keeps running.
        """
        with self._lock:
            before = self._db.execute(
                "SELECT COUNT(*) FROM telemetry WHERE plant_id=?", (plant_id,)
            ).fetchone()[0]
            self._db.execute(
                "DELETE FROM telemetry WHERE plant_id=? AND id NOT IN"
                " (SELECT id FROM telemetry WHERE plant_id=? ORDER BY id DESC LIMIT ?)",
                (plant_id, plant_id, keep),
            )
            self._db.commit()
        return max(0, int(before) - keep)

    # --------------------------------------------------------------- domain

    def record_fault(
        self,
        fault_id: str,
        plant_id: str,
        equipment_id: str,
        sensor_id: str | None,
        mode_id: str,
        mechanism: str,
        detail: dict,
        sim_t: float,
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO fault_events"
            " (id,plant_id,equipment_id,sensor_id,mode_id,mechanism,detail,sim_t,wall_ts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                fault_id,
                plant_id,
                equipment_id,
                sensor_id,
                mode_id,
                mechanism,
                json.dumps(detail),
                sim_t,
                time.time(),
            ),
        )

    def upsert_incident(self, incident: Any, fault_event_id: str | None = None) -> None:
        d = incident.model_dump() if hasattr(incident, "model_dump") else dict(incident)
        now = time.time()
        self._exec(
            "INSERT INTO incidents (id,plant_id,title,severity,status,origin_equipment,origin_sensor,"
            "failure_mode,affected,fault_event_id,created_at,resolved_at,wall_created,wall_updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status, affected=excluded.affected,"
            " resolved_at=excluded.resolved_at, wall_updated=excluded.wall_updated",
            (
                d["id"],
                d["plant_id"],
                d["title"],
                _v(d["severity"]),
                _v(d["status"]),
                d["origin_equipment"],
                d.get("origin_sensor"),
                d.get("failure_mode"),
                json.dumps(d.get("affected", [])),
                fault_event_id,
                d.get("created_at", 0.0),
                d.get("resolved_at"),
                now,
                now,
            ),
        )

    def start_execution(
        self,
        execution_id: str,
        incident_id: str,
        plant_id: str,
        runtime: str,
        orchestrator: str = "orchestrator",
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO agent_executions"
            " (id,incident_id,plant_id,orchestrator,runtime,status,task_count,started_at,completed_at)"
            " VALUES (?,?,?,?,?,?,?,?,NULL)",
            (execution_id, incident_id, plant_id, orchestrator, runtime, "running", 0, time.time()),
        )

    def finish_execution(self, execution_id: str, status: str, task_count: int) -> None:
        self._exec(
            "UPDATE agent_executions SET status=?, task_count=?, completed_at=? WHERE id=?",
            (status, task_count, time.time(), execution_id),
        )

    def upsert_task(self, execution_id: str, task: Any) -> None:
        d = task.model_dump() if hasattr(task, "model_dump") else dict(task)
        self._exec(
            "INSERT INTO agent_tasks (id,execution_id,incident_id,agent,title,status,sequence,"
            "depends_on,tools,result,started_at,completed_at,wall_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status, result=excluded.result,"
            " tools=excluded.tools, completed_at=excluded.completed_at",
            (
                d["id"],
                execution_id,
                d["incident_id"],
                d["agent"],
                d["title"],
                d["status"],
                d.get("sequence", 0),
                json.dumps(d.get("depends_on", [])),
                json.dumps(d.get("tools", [])),
                d.get("result"),
                d.get("started_at"),
                d.get("completed_at"),
                time.time(),
            ),
        )

    def add_evidence(self, task_id: str, incident_id: str, ev: Any) -> None:
        d = ev.model_dump() if hasattr(ev, "model_dump") else dict(ev)
        self._exec(
            "INSERT OR REPLACE INTO agent_evidence"
            " (id,task_id,incident_id,source_type,source_id,description,confidence,citation,wall_ts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                d["id"],
                task_id,
                incident_id,
                d["source_type"],
                d["source_id"],
                d["description"],
                d.get("confidence", 0.9),
                d.get("citation"),
                time.time(),
            ),
        )

    def request_approval(
        self,
        approval_id: str,
        incident_id: str,
        reason: str,
        plan: dict,
        requested_by: str = "orchestrator",
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO approvals"
            " (id,incident_id,requested_by,reason,plan,status,decided_by,requested_at,decided_at)"
            " VALUES (?,?,?,?,?,?,NULL,?,NULL)",
            (
                approval_id,
                incident_id,
                requested_by,
                reason,
                json.dumps(plan),
                "requested",
                time.time(),
            ),
        )

    def decide_approval(
        self, approval_id: str, granted: bool, decided_by: str = "operator"
    ) -> None:
        self._exec(
            "UPDATE approvals SET status=?, decided_by=?, decided_at=? WHERE id=?",
            ("granted" if granted else "rejected", decided_by, time.time(), approval_id),
        )

    def start_action(
        self,
        action_id: str,
        incident_id: str,
        approval_id: str | None,
        kind: str,
        target: str,
        executor: str,
        policy: str,
        policy_reason: str | None,
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO actions"
            " (id,incident_id,approval_id,kind,target,executor,policy,policy_reason,status,result,started_at,completed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,NULL,?,NULL)",
            (
                action_id,
                incident_id,
                approval_id,
                kind,
                target,
                executor,
                policy,
                policy_reason,
                "started" if policy == "allowed" else "blocked",
                time.time(),
            ),
        )

    def finish_action(self, action_id: str, status: str, result: dict) -> None:
        self._exec(
            "UPDATE actions SET status=?, result=?, completed_at=? WHERE id=?",
            (status, json.dumps(result), time.time(), action_id),
        )

    def record_verification(
        self,
        verification_id: str,
        incident_id: str,
        action_id: str | None,
        passed: bool,
        findings: list[str],
        checks_run: int,
        sim_t: float,
    ) -> None:
        self._exec(
            "INSERT OR REPLACE INTO verification_results"
            " (id,incident_id,action_id,passed,findings,checks_run,sim_t,wall_ts)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                verification_id,
                incident_id,
                action_id,
                1 if passed else 0,
                json.dumps(findings),
                checks_run,
                sim_t,
                time.time(),
            ),
        )

    def record_artifact(self, artifact: dict, incident_id: str) -> None:
        self._exec(
            "INSERT OR REPLACE INTO artifacts"
            " (id,incident_id,kind,filename,verified,sources,body,created_at,wall_ts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                artifact["id"],
                incident_id,
                artifact.get("kind", "incident_report"),
                artifact["filename"],
                1 if artifact.get("verified") else 0,
                artifact.get("sources", 0),
                artifact.get("body"),
                artifact.get("created_at", 0.0),
                time.time(),
            ),
        )

    def audit(
        self,
        *,
        event_type: str,
        actor: str,
        plant_id: str | None = None,
        incident_id: str | None = None,
        sim_t: float | None = None,
        task_id: str | None = None,
        action: str | None = None,
        target: str | None = None,
        result: str | None = None,
        approval_id: str | None = None,
        verification_id: str | None = None,
        evidence_count: int = 0,
        runtime: str | None = None,
        payload: dict | None = None,
    ) -> int:
        cur = self._exec(
            "INSERT INTO audit_events (wall_ts,sim_t,plant_id,incident_id,actor,event_type,task_id,"
            "action,target,result,approval_id,verification_id,evidence_count,runtime,payload)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                time.time(),
                sim_t,
                plant_id,
                incident_id,
                actor,
                event_type,
                task_id,
                action,
                target,
                result,
                approval_id,
                verification_id,
                evidence_count,
                runtime,
                json.dumps(payload or {}, default=str),
            ),
        )
        return int(cur.lastrowid or 0)

    # ------------------------------------------------------------- read API

    def incident_history(self, plant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Incident list for a plant, newest first, read from disk.

        Each row carries the counts that prove the pipeline ran: tasks,
        evidence, actions, verifications and audit events.
        """
        return self.query(
            "SELECT i.*,"
            " (SELECT COUNT(*) FROM agent_tasks t WHERE t.incident_id=i.id) AS task_count,"
            " (SELECT COUNT(*) FROM agent_evidence e WHERE e.incident_id=i.id) AS evidence_count,"
            " (SELECT COUNT(*) FROM actions a WHERE a.incident_id=i.id) AS action_count,"
            " (SELECT COUNT(*) FROM verification_results v WHERE v.incident_id=i.id) AS verification_count,"
            " (SELECT COUNT(*) FROM audit_events x WHERE x.incident_id=i.id) AS audit_count"
            " FROM incidents i WHERE i.plant_id=? ORDER BY i.wall_created DESC LIMIT ?",
            (plant_id, limit),
        )

    def audit_events(
        self, plant_id: str | None = None, incident_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if plant_id:
            clauses.append("plant_id=?")
            params.append(plant_id)
        if incident_id:
            clauses.append("incident_id=?")
            params.append(incident_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        return self.query(
            f"SELECT * FROM audit_events{where} ORDER BY id DESC LIMIT ?", tuple(params)
        )

    def incident_record(self, incident_id: str) -> dict[str, Any] | None:
        record = self._incident_record(incident_id)
        return record if record["incident"] else None

    def _incident_record(self, incident_id: str) -> dict[str, Any]:
        """Everything the Command Center needs, straight from disk."""
        inc = self.query("SELECT * FROM incidents WHERE id=?", (incident_id,))
        return {
            "incident": inc[0] if inc else None,
            "executions": self.query(
                "SELECT * FROM agent_executions WHERE incident_id=?", (incident_id,)
            ),
            "tasks": self.query(
                "SELECT * FROM agent_tasks WHERE incident_id=? ORDER BY sequence", (incident_id,)
            ),
            "evidence": self.query(
                "SELECT * FROM agent_evidence WHERE incident_id=?", (incident_id,)
            ),
            "approvals": self.query("SELECT * FROM approvals WHERE incident_id=?", (incident_id,)),
            "actions": self.query("SELECT * FROM actions WHERE incident_id=?", (incident_id,)),
            "verifications": self.query(
                "SELECT * FROM verification_results WHERE incident_id=?", (incident_id,)
            ),
            "artifacts": self.query("SELECT * FROM artifacts WHERE incident_id=?", (incident_id,)),
            "audit": self.query(
                "SELECT * FROM audit_events WHERE incident_id=? ORDER BY id", (incident_id,)
            ),
        }


def _v(x: Any) -> str:
    return x.value if hasattr(x, "value") else str(x)


_store: SimulationStore | None = None


def get_store(path: str | Path | None = None) -> SimulationStore:
    """Process-wide store. Tests pass an explicit path (or ``:memory:``)."""
    global _store
    if path is not None:
        return SimulationStore(path)
    if _store is None:
        _store = SimulationStore()
    return _store
