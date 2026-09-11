"""Industrial simulation (digital twin) — Phase SIM.

A real, stateful simulation environment wired into Project 117's existing
infrastructure: telemetry ticks feed the same event-bus discipline the job
system uses (persist first, publish second), incidents are decomposed by the
orchestrator into agent tasks, actions pass the approval gate, and everything
is verified and audited.

Nothing in here is a pre-recorded script. The engine is a deterministic
state machine: same seed + same inputs = same plant behavior. Failure
propagation follows the topology graph, not a storyline.

Modules:
    models      — domain contracts (Pydantic), shared with the frontend
    engine      — tick loop, telemetry, alarms, failure propagation
    agents      — deterministic multi-agent incident pipeline
    service     — lifecycle + orchestration + persistence seams
    datasets    — loader/validator for data/simulation/*.json
    api         — FastAPI router (/api/simulation/*) + SSE stream
"""

from backend.simulation.engine import SimulationEngine
from backend.simulation.models import (
    Alarm,
    AlarmSeverity,
    AssetState,
    Connection,
    ConnectionKind,
    Equipment,
    EquipmentKind,
    FailureMode,
    Incident,
    IncidentStatus,
    Measurement,
    Plant,
    PlantArea,
    Scenario,
    Sensor,
    SimulationEvent,
    TelemetryPoint,
)

__all__ = [
    "Alarm",
    "AlarmSeverity",
    "AssetState",
    "Connection",
    "ConnectionKind",
    "Equipment",
    "EquipmentKind",
    "FailureMode",
    "Incident",
    "IncidentStatus",
    "Measurement",
    "Plant",
    "PlantArea",
    "Scenario",
    "Sensor",
    "SimulationEngine",
    "SimulationEvent",
    "TelemetryPoint",
]
