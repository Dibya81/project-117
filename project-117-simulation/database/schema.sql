-- Project 117 simulation — schema for the prebuilt plant datasets.
-- Target: SQLite (matches Project 117's existing app database).

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    plant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sequence INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    id TEXT PRIMARY KEY,
    plant_id TEXT NOT NULL,
    zone_id TEXT NOT NULL REFERENCES zones(id),
    tag TEXT NOT NULL,
    type TEXT NOT NULL,                 -- pump, valve, tank, heat_exchanger, compressor,
                                         -- column, reactor, furnace, conveyor, motor,
                                         -- compressor_blower, caster, mill_stand
    install_date TEXT NOT NULL,
    expected_lifespan_years INTEGER NOT NULL,
    last_inspection TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'normal',   -- normal | warning | critical | disabled
    failure_modes TEXT NOT NULL              -- comma-separated
);

CREATE TABLE IF NOT EXISTS sensors (
    id TEXT PRIMARY KEY,
    equipment_id TEXT NOT NULL REFERENCES equipment(id),
    tag TEXT NOT NULL,
    type TEXT NOT NULL,             -- PT, TT, FT, LT, VT
    label TEXT NOT NULL,
    unit TEXT NOT NULL,
    normal_min REAL NOT NULL,
    normal_max REAL NOT NULL,
    current_value REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    plant_id TEXT NOT NULL,
    source_id TEXT NOT NULL,   -- equipment.id or sensor.id
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL         -- pipe (process flow) | wire (signal)
);

-- Live/runtime tables — written to by the orchestrator during a fault demo,
-- read by the frontend to render the agent trace and audit history.

CREATE TABLE IF NOT EXISTS fault_events (
    id TEXT PRIMARY KEY,
    plant_id TEXT NOT NULL,
    equipment_id TEXT NOT NULL REFERENCES equipment(id),
    fault_type TEXT NOT NULL,        -- disabled | removed | sensor_drift | leak
    triggered_at TEXT NOT NULL,
    job_id TEXT                      -- FK to Project 117's own `jobs` table
);

CREATE TABLE IF NOT EXISTS agent_trace_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    fault_event_id TEXT REFERENCES fault_events(id),
    stage TEXT NOT NULL,             -- perceive | plan | act | verify | complete | recover
    label TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_equipment_zone ON equipment(zone_id);
CREATE INDEX IF NOT EXISTS idx_sensors_equipment ON sensors(equipment_id);
CREATE INDEX IF NOT EXISTS idx_connections_plant ON connections(plant_id);
CREATE INDEX IF NOT EXISTS idx_trace_job ON agent_trace_events(job_id);
