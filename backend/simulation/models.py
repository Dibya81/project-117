"""Simulation domain contracts.

One definition per concept, imported by the engine, the API, the dataset
generator/validator, and mirrored 1:1 in
``apps/web/src/lib/sim/types.ts`` — the SSE wire format is these models'
JSON.

Tagging convention (documented, not random):
    P-/PU-    pumps              TK-   tanks
    V-        valves             VS-   vessels / separators
    E-        heat exchangers    C-    compressors
    COL-      columns            F-    furnaces / boilers
    M-        motors/fans        CV-   conveyors
    PT/TT/FT/LT/AT-...  transmitters (ISA-5.1 lettering, original symbols)
    VIB-/RPM-/A-/KW-   machinery instruments
    GD-/LK-   gas / leak detectors      XV-/ESD-  safety

Everything synthetic: the plants are demonstration plants, and every payload
carries ``source: "synthetic-simulation"``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

SOURCE = "synthetic-simulation"


class EquipmentKind(str, Enum):
    PUMP = "pump"
    VALVE = "valve"
    TANK = "tank"
    VESSEL = "vessel"
    COLUMN = "column"
    EXCHANGER = "exchanger"
    FURNACE = "furnace"
    COMPRESSOR = "compressor"
    MOTOR = "motor"
    CONVEYOR = "conveyor"
    SAFETY = "safety"
    UTILITY = "utility"


class Measurement(str, Enum):
    PRESSURE = "pressure"        # bar
    TEMPERATURE = "temperature"  # degC
    FLOW = "flow"                # m3/h
    LEVEL = "level"              # %
    VIBRATION = "vibration"      # mm/s
    RPM = "rpm"                  # rpm
    CURRENT = "current"          # A
    POWER = "power"              # kW
    GAS = "gas"                  # ppm
    LEAK = "leak"                # bool-ish 0/1
    POSITION = "position"        # %
    SPEED = "speed"              # m/s (conveyors)


UNITS: dict[Measurement, str] = {
    Measurement.PRESSURE: "bar",
    Measurement.TEMPERATURE: "°C",
    Measurement.FLOW: "m³/h",
    Measurement.LEVEL: "%",
    Measurement.VIBRATION: "mm/s",
    Measurement.RPM: "rpm",
    Measurement.CURRENT: "A",
    Measurement.POWER: "kW",
    Measurement.GAS: "ppm",
    Measurement.LEAK: "0/1",
    Measurement.POSITION: "%",
    Measurement.SPEED: "m/s",
}


class AssetState(str, Enum):
    """Visual + behavioral state of any simulated asset.

    NORMAL..DISABLED are plant states; INVESTIGATING..VERIFIED are agent
    overlays the UI renders as rings/indicators without recoloring the asset.
    """

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"
    DISABLED = "disabled"
    INVESTIGATING = "investigating"
    ACTING = "acting"
    VERIFYING = "verifying"
    VERIFIED = "verified"


class TelemetryQuality(str, Enum):
    GOOD = "good"
    BAD = "bad"          # sensor failed — value must not be trusted
    STALE = "stale"
    SUBSTITUTED = "substituted"  # value comes from a validated alternate


class Sensor(BaseModel):
    """One measurement point. Thresholds define the operating envelope."""

    id: str
    tag: str
    equipment_id: str
    measurement: Measurement
    unit: str
    nominal: float
    normal_min: float
    normal_max: float
    warning_min: float
    warning_max: float
    critical_min: float
    critical_max: float
    sampling_ms: int = 1000
    # noise as a fraction of (normal_max - normal_min) per tick
    noise: float = 0.012
    # drift rate per tick when its failure mode is injected (units/tick)
    drift_rate: float = 0.0
    is_detector: bool = False  # gas/leak style point sensors (0/1, latched)


class TelemetryPoint(BaseModel):
    sensor_id: str
    value: float
    quality: TelemetryQuality
    t: float  # simulation seconds since start


class FailureMode(BaseModel):
    """A named, injectable failure. `effects` drive propagation:
    sensor    — target sensor dies (quality=BAD, value frozen/NaN)
    drift     — target sensor drifts at drift_rate until out of envelope
    degrade   — equipment capacity factor drops to `magnitude`
    stop      — equipment stops (capacity 0), dependent flow collapses
    leak      — medium lost at `magnitude` fraction of connected flow
    surge     — connected pressures jump by `magnitude` fraction
    """

    id: str
    name: str
    applies_to: list[str]  # equipment kinds or measurement names
    mechanism: str  # sensor|drift|degrade|stop|leak|surge
    magnitude: float = 1.0
    description: str = ""


class Equipment(BaseModel):
    id: str
    tag: str
    name: str
    kind: EquipmentKind
    area_id: str
    x: float
    y: float
    criticality: int = 2  # 1 low .. 3 high
    capacity: float = 1.0  # 0..1 running capacity factor (engine state)
    state: AssetState = AssetState.NORMAL
    sensors: list[Sensor] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)  # FailureMode ids
    # provenance-flavored synthetic metadata
    manufacturer: str = "SynthWorks"
    model: str = "SW-100"
    installed: str = "2019-01-01"
    last_inspection: str = "2026-06-01"


class ConnectionKind(str, Enum):
    PIPE = "pipe"        # process medium flows here — failure propagates
    SIGNAL = "signal"    # instrumentation wiring — no process flow
    CONTROL = "control"  # controller → actuator
    POWER = "power"      # electrical feed


class Connection(BaseModel):
    id: str
    kind: ConnectionKind
    source: str  # equipment id
    target: str  # equipment id
    medium: str = "process"  # crude|water|steam|gas|ore|air…
    capacity: float = 100.0  # m3/h nominal
    flow: float = 0.0        # engine state (m3/h equivalent)
    status: AssetState = AssetState.NORMAL
    leaking: bool = False
    enabled: bool = True


class PlantArea(BaseModel):
    id: str
    name: str
    x: float
    y: float
    w: float
    h: float


class Plant(BaseModel):
    id: str
    name: str
    industry: str
    areas: list[PlantArea]
    equipment: list[Equipment]
    connections: list[Connection]
    failure_modes: list[FailureMode]


class AlarmSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class Alarm(BaseModel):
    id: str
    sensor_id: str
    tag: str
    severity: AlarmSeverity
    message: str
    at: float
    active: bool = True


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    PLAN_READY = "plan_ready"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTING = "acting"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class Incident(BaseModel):
    id: str
    plant_id: str
    title: str
    severity: AlarmSeverity
    status: IncidentStatus
    origin_equipment: str
    origin_sensor: str | None = None
    failure_mode: str | None = None
    affected: list[str] = Field(default_factory=list)  # equipment ids
    created_at: float = 0.0
    resolved_at: float | None = None


class SimulationEvent(BaseModel):
    """One persisted event on the simulation bus (see §33 of the spec)."""

    seq: int
    plant_id: str
    type: str  # sensor.failed | equipment.state_changed | incident.created | …
    payload: dict = Field(default_factory=dict)
    at: float


class ScenarioStep(BaseModel):
    at_s: float
    action: str  # inject_failure:<mode>:<target> | note:<text>
    target: str | None = None


class Scenario(BaseModel):
    id: str
    name: str
    description: str
    steps: list[ScenarioStep]
