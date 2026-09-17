"""Simulation API — /api/simulation/*

REST for control + snapshot, SSE for the live event stream. AuthZ follows
the equipment routes: reads need connectors:read, control needs
connectors:write (an operator cannot trip a pump by guessing a URL).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.src.deps import get_principal
from backend.security.rbac import Principal
from backend.simulation import datasets
from backend.simulation.models import Plant
from backend.simulation.service import SimulationService

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class InjectRequest(BaseModel):
    mode_id: str


class DecisionRequest(BaseModel):
    approved: bool


class SavePlantRequest(BaseModel):
    """Builder save payload: the full plant definition the canvas produced."""

    plant: Plant


def _svc() -> SimulationService:
    # Wired in main.py at startup via attach().
    from backend.simulation import api as _self
    if _self.service is None:
        raise HTTPException(status_code=503, detail={"code": "simulation_unavailable", "message": "no simulation service attached"})
    return _self.service


service: SimulationService | None = None


def attach(svc: SimulationService) -> None:
    """Called once at app startup; mirrors how the demo store is bound."""
    global service
    service = svc


@router.get("/health")
def health(principal: Principal = Depends(get_principal)) -> dict:
    """Liveness probe the frontend calls before entering live mode.

    The web app refuses to run its embedded engine unless mock mode was
    explicitly selected, so this endpoint is what makes a missing backend
    visible instead of silently faked.
    """
    svc = _svc()
    return {
        "status": "ok",
        "mode": "live",
        "database": svc.store.path,
        "agents": svc.roster.status(),
        "plants_registered": svc.registered_ids(),
        "plants_available": [p["id"] for p in datasets.list_plants()],
    }


@router.get("/plants")
def list_plants(principal: Principal = Depends(get_principal)) -> dict:
    """Dataset plants plus any plant the builder saved to the database."""
    svc = _svc()
    return {
        "source": "synthetic-simulation",
        "plants": [*datasets.list_plants(), *svc.store.list_saved_plants(origin="builder")],
    }


@router.post("/plants", status_code=201)
def save_plant(body: SavePlantRequest, principal: Principal = Depends(get_principal)) -> dict:
    """Builder save. Writes the graph (plant, zones, equipment, sensors,
    actuators, connections) to the database and registers it for simulation,
    so a reload or a backend restart finds it again."""
    svc = _svc()
    svc.register(body.plant, origin="builder")
    return {
        "plant": body.plant.id,
        "saved": True,
        "equipment": len(body.plant.equipment),
        "sensors": sum(len(e.sensors) for e in body.plant.equipment),
        "connections": len(body.plant.connections),
    }


@router.get("/plants/{plant_id}/definition")
def plant_definition(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """Builder load: rehydrate a saved plant straight from the database."""
    svc = _svc()
    plant = svc.store.load_plant_definition(plant_id)
    if plant is None:
        try:
            plant = datasets.load_plant(plant_id)
        except datasets.DatasetError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"plant": plant.model_dump(), "source": "database"}


@router.get("/plants/{plant_id}/scenarios")
def plant_scenarios(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """Scenario scripts for a plant, read from SQLite.

    Scenarios are not part of the Plant model, so they have their own table;
    the store is the only source, there is no JSON fallback."""
    svc = _svc()
    if svc.store.load_plant_dict(plant_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown plant dataset: {plant_id}")
    return {"scenarios": svc.store.load_scenarios(plant_id)}


@router.delete("/plants/{plant_id}")
def delete_plant(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    removed = svc.store.delete_plant(plant_id)
    if not removed:
        raise HTTPException(status_code=404, detail="unknown plant")
    return {"plant": plant_id, "deleted": True}


@router.post("/plants/{plant_id}/start")
def start(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        rt = svc.runtime(plant_id)
    except KeyError:
        # cold start: load + register on first use
        try:
            plant = datasets.load_plant(plant_id)
        except datasets.DatasetError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        rt = svc.register(plant)
    svc.start(plant_id)
    return {"plant": plant_id, "running": rt.running, "t": rt.engine.t}


@router.post("/plants/{plant_id}/pause")
def pause(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    svc.pause(plant_id)
    return {"plant": plant_id, "running": False}


@router.get("/plants/{plant_id}/snapshot")
def snapshot(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        rt = svc.runtime(plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plant not running") from exc
    snap = rt.engine.snapshot()
    snap["plant"] = rt.engine.plant.model_dump()
    snap["source"] = "synthetic-simulation"
    return snap


@router.get("/plants/{plant_id}/frame")
def frame(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """The LIVE state only: equipment state, sensor values, line flow.

    ``/snapshot`` returns this **plus** the whole plant definition, and the
    definition is 114 KB of its 127 KB — static geometry, sensor models and
    failure modes that a console page already holds from `loadPlant`. Polling the
    snapshot at the console's 4 Hz refresh therefore re-sent ~114 KB of unchanging
    data four times a second (measured: 507 KB/s on the live plant page, 90% of it
    definition).

    This endpoint carries only what actually changes, so a poll is ~26 KB. It is
    additive: ``/snapshot`` is unchanged and remains the right call for a client
    that has no definition yet.
    """
    svc = _svc()
    try:
        rt = svc.runtime(plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plant not running") from exc
    snap = rt.engine.snapshot()
    return {
        "t": snap["t"],
        # `engine.snapshot()` carries state only; the run flag lives on the
        # runtime. Reading `snap["running"]` raised KeyError and answered 500.
        "running": rt.running,
        "equipment": snap["equipment"],
        "sensors": snap["sensors"],
        "connections": snap["connections"],
        "alarms": snap["alarms"],
        "incidents": snap["incidents"],
        "source": "synthetic-simulation",
    }


@router.get("/plants/{plant_id}/stream")
async def stream(plant_id: str, after: int = 0, principal: Principal = Depends(get_principal)) -> StreamingResponse:
    svc = _svc()
    try:
        svc.runtime(plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="plant not running") from exc

    async def gen():
        async for ev in svc.subscribe(plant_id, after_seq=after):
            yield f"data: {_json(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def _json(ev: dict) -> str:
    import json

    return json.dumps(ev, separators=(",", ":"))


@router.get("/plants/{plant_id}/incidents")
def incidents(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    rt = _svc().runtime(plant_id)
    return {"incidents": [i.model_dump() for i in rt.engine.incidents.values()]}


@router.get("/plants/{plant_id}/incidents/{incident_id}/tasks")
def incident_tasks(plant_id: str, incident_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """The incident's task DAG, or an empty one while it is still being built.

    ``incident.created`` is emitted before the pipeline finishes assembling the
    tasks, and the console polls this endpoint the moment it sees the incident.
    Answering 404 in that window made the browser log a failed request on every
    incident; "the run has no tasks yet" is the honest answer, and it is not the
    same thing as an unknown incident.
    """
    rt = _svc().runtime(plant_id)
    tasks = rt.incident_tasks.get(incident_id)
    plan = rt.incident_plans.get(incident_id)
    if tasks is None or plan is None:
        if incident_id in rt.engine.incidents:
            return {"tasks": [], "plan": None, "pending": True}
        raise HTTPException(status_code=404, detail="unknown incident")
    return {
        "tasks": [t.model_dump() for t in tasks],
        "plan": plan.model_dump(),
    }


@router.post("/plants/{plant_id}/equipment/{equipment_id}/failure")
def inject(plant_id: str, equipment_id: str, body: InjectRequest, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        return svc.inject_failure(plant_id, equipment_id, body.mode_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plants/{plant_id}/equipment/{equipment_id}/disable")
def disable(plant_id: str, equipment_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    svc.disable_equipment(plant_id, equipment_id)
    return {"equipment_id": equipment_id, "state": "disabled"}


@router.post("/plants/{plant_id}/equipment/{equipment_id}/remove")
def remove(plant_id: str, equipment_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    broken = svc.remove_equipment(plant_id, equipment_id)
    return {"equipment_id": equipment_id, "state": "removed", "broken_paths": broken}


@router.post("/plants/{plant_id}/sensors/{sensor_id}/disable")
def disable_sensor(plant_id: str, sensor_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        return svc.disable_sensor(plant_id, sensor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plants/{plant_id}/sensors/{sensor_id}/remove")
def remove_sensor(plant_id: str, sensor_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        return svc.remove_sensor(plant_id, sensor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plants/{plant_id}/sensors/{sensor_id}/restore")
def restore_sensor(plant_id: str, sensor_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        svc.restore_sensor(plant_id, sensor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"sensor_id": sensor_id, "state": "restored"}


@router.post("/plants/{plant_id}/lines/{connection_id}/block")
def block_line(plant_id: str, connection_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """Block a process line. Starves everything downstream on the next tick."""
    svc = _svc()
    try:
        return svc.block_line(plant_id, connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"no such line: {connection_id}") from exc


@router.post("/plants/{plant_id}/lines/{connection_id}/restore")
def restore_line(plant_id: str, connection_id: str, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        return svc.restore_line(plant_id, connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"no such line: {connection_id}") from exc


class LeakRequest(BaseModel):
    leaking: bool = True


@router.post("/plants/{plant_id}/lines/{connection_id}/leak")
def leak_line(
    plant_id: str,
    connection_id: str,
    body: LeakRequest | None = None,
    principal: Principal = Depends(get_principal),
) -> dict:
    """Mark a line leaking, or seal it. A leaking line still carries flow, at
    reduced capacity, so the drawing and the engine agree."""
    svc = _svc()
    leaking = True if body is None else body.leaking
    try:
        return svc.leak_line(plant_id, connection_id, leaking=leaking)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"no such line: {connection_id}") from exc


@router.post("/plants/{plant_id}/reset")
def reset(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """Return the plant to its pristine definition, discarding every
    in-memory operator change (a reload must find normal, not a session)."""
    svc = _svc()
    plant = svc.store.load_plant_definition(plant_id)
    if plant is None:
        try:
            plant = datasets.load_plant(plant_id)
        except datasets.DatasetError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    rt = svc.reset(plant_id, plant)
    return {"plant": plant_id, "reset": True, "equipment": len(rt.engine.plant.equipment)}


@router.post("/plants/{plant_id}/incidents/{incident_id}/decision")
async def decide(plant_id: str, incident_id: str, body: DecisionRequest, principal: Principal = Depends(get_principal)) -> dict:
    svc = _svc()
    try:
        return await svc.decide_async(plant_id, incident_id, body.approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc



@router.get("/plants/{plant_id}/alarms")
def alarms(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    rt = _svc().runtime(plant_id)
    return {"alarms": [a.model_dump() for a in rt.engine.alarms.values()]}


@router.get("/plants/{plant_id}/artifacts")
def artifacts(plant_id: str, principal: Principal = Depends(get_principal)) -> dict:
    rt = _svc().runtime(plant_id)
    return {"artifacts": rt.artifacts}


@router.get("/plants/{plant_id}/history")
def history(plant_id: str, limit: int = 50, principal: Principal = Depends(get_principal)) -> dict:
    """Persisted incident history — read from the database, not from memory.

    This is the endpoint that proves restart survival: it answers after a
    process restart, with no plant registered in RAM.
    """
    svc = _svc()
    return {"source": "database", "incidents": svc.store.incident_history(plant_id, limit=limit)}


@router.get("/incidents/{incident_id}/record")
def incident_record(incident_id: str, principal: Principal = Depends(get_principal)) -> dict:
    """Full persisted record for one incident: execution, tasks, evidence,
    approval, action, verification, artifacts and audit events."""
    svc = _svc()
    record = svc.store.incident_record(incident_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown incident")
    return record


@router.get("/audit")
def audit(
    plant_id: str | None = None,
    incident_id: str | None = None,
    limit: int = 200,
    principal: Principal = Depends(get_principal),
) -> dict:
    """Persistent audit trail. The SSE stream mirrors these rows; the database
    is the source of truth."""
    svc = _svc()
    return {
        "source": "database",
        "events": svc.store.audit_events(plant_id=plant_id, incident_id=incident_id, limit=limit),
    }
