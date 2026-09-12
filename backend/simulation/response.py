"""Derived beats for the Agent Response Console's three lanes.

The raw agent pipeline emits task/tool/evidence events. The console also needs
a handful of *response beats* that the raw events cannot express (which
department was notified, which alternate was actually chosen, the maintenance
counts, the closing user notification). Every field below is computed from the
engine's real plant graph, live sensor state and the pipeline's own task
records — nothing is scripted and no field is invented in the frontend.

WHY a separate module: the derivations are pure functions over engine state, so
they can be unit-tested without the API and the service stays readable.
"""

from __future__ import annotations

from backend.simulation.agents import AgentTask
from backend.simulation.assessment import predict_next_failure, years_since
from backend.simulation.engine import SimulationEngine
from backend.simulation.models import FailureMode, Incident, Sensor, TelemetryQuality


def resolve_department(engine: SimulationEngine, equipment_id: str) -> dict:
    """Which department owns an asset.

    WHY this derivation: the plant model has no department/organisation table.
    The only real ownership data is ``Equipment.area_id -> PlantArea.name``, so
    the responsible department is the process area that owns the asset. When
    the area is missing we fall back to the raw area id, and the payload says
    which field was used, so the console can be honest about it.
    """
    eq = next((e for e in engine.plant.equipment if e.id == equipment_id), None)
    if eq is None:
        return {"department": "Operations", "department_source": "fallback"}
    area = next((a for a in engine.plant.areas if a.id == eq.area_id), None)
    if area is None:
        return {"department": eq.area_id or "Operations", "department_source": "equipment.area_id"}
    return {"department": area.name, "department_source": "plant_area.name"}


def choose_failover(engine: SimulationEngine, origin_sensor_id: str | None) -> Sensor | None:
    """The alternate measurement the pipeline would actually switch to.

    Reuses ``engine.alternate_sensors`` — the same redundancy reasoning the data
    analysis agent runs — and keeps only points that exist in the running plant,
    are in service and read GOOD. When several qualify we prefer one on a
    *different* asset, because that survives loss of the whole instrument family
    and local wiring; if none exists a second transmitter on the same asset is
    still a valid failover. Returns the chosen ``Sensor`` model, or None when no
    alternate can carry the measurement — in which case the console must report
    a no-response rather than a fabricated switch.
    """
    if not origin_sensor_id or origin_sensor_id not in engine.sensors:
        return None
    origin_equipment = engine.sensor_model[origin_sensor_id].equipment_id
    usable: list[Sensor] = []
    for sensor in engine.alternate_sensors(origin_sensor_id):
        rt = engine.sensors.get(sensor.id)
        if rt is None or rt.failed or rt.quality != TelemetryQuality.GOOD:
            continue
        if engine.sensor_out_of_service(sensor.id) is not None:
            continue
        usable.append(sensor)
    if not usable:
        return None
    cross_asset = next((s for s in usable if s.equipment_id != origin_equipment), None)
    return cross_asset or usable[0]


def failover_candidates(engine: SimulationEngine, origin_sensor_id: str | None) -> list[dict]:
    """Every alternate considered, with the live quality that qualified it."""
    if not origin_sensor_id or origin_sensor_id not in engine.sensors:
        return []
    origin_equipment = engine.sensor_model[origin_sensor_id].equipment_id
    out: list[dict] = []
    for sensor in engine.alternate_sensors(origin_sensor_id):
        rt = engine.sensors.get(sensor.id)
        if rt is None:
            continue
        out.append({
            "sensor_id": sensor.id,
            "tag": sensor.tag,
            "equipment_id": sensor.equipment_id,
            "measurement": sensor.measurement.value,
            "quality": rt.quality.value,
            "in_service": engine.sensor_out_of_service(sensor.id) is None and not rt.failed,
            "same_asset": sensor.equipment_id == origin_equipment,
        })
    return out


def maintenance_counts(engine: SimulationEngine, incident: Incident, tasks: list[AgentTask]) -> dict:
    """Counts backing the "reviewing maintenance and inspection history" beat.

    WHY only these counts: the store has no work-order or inspection-report
    table. What genuinely exists is the maintenance evidence the pipeline
    recorded for this incident, the documents retrieval returned, and the
    asset's own failure-mode list plus its inspection date. Reporting anything
    else (a work-order count) would be a fabricated field, so the payload names
    exactly what was counted.
    """
    eq = next((e for e in engine.plant.equipment if e.id == incident.origin_equipment), None)
    maintenance_records = sum(
        1 for t in tasks for e in t.evidence if e.source_type == "maintenance"
    )
    documents_retrieved = sum(1 for t in tasks for e in t.evidence if e.source_type == "documents")
    years = years_since(eq.last_inspection) if eq else None
    return {
        "maintenance_records": maintenance_records,
        "documents_retrieved": documents_retrieved,
        "failure_modes_known": len(eq.failure_modes) if eq else 0,
        "last_inspection": eq.last_inspection if eq else None,
        "years_since_inspection": round(years, 1) if years is not None else None,
    }


def build_user_summary(
    equipment_tag: str,
    mode: FailureMode | None,
    failover: Sensor | None,
    prediction: dict,
) -> str:
    """The closing user-facing notification, assembled from real fields only."""
    fault = mode.name if mode is not None else "measurement loss"
    parts = [f"{equipment_tag}: {fault} confirmed."]
    if failover is not None:
        parts.append(f"Control input switched to {failover.tag} ({failover.equipment_id}).")
    else:
        parts.append("No validated alternate measurement available — manual intervention required.")
    candidates = prediction.get("candidates") or []
    if candidates:
        top = candidates[0]
        parts.append(f"Next at risk: {top['tag']} ({round(top['risk'] * 100)}%).")
    return " ".join(parts)


__all__ = [
    "build_user_summary",
    "choose_failover",
    "failover_candidates",
    "maintenance_counts",
    "predict_next_failure",
    "resolve_department",
]
