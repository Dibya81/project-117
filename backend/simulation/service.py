"""Simulation service — lifecycle, orchestration, and the event stream.

Follows the job-bus discipline from ``backend/jobs/bus.py``: events are
appended to a durable per-plant log *first* (late joiners replay by
sequence), then published to subscribers. The engine never waits on a
consumer; a slow subscriber is dropped with an overflow marker.

One ``SimulationService`` owns one engine per running plant. The asyncio
tick loop lives here, so tests can drive ``step()`` synchronously without a
loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.simulation.actions import execute_action
from backend.simulation.agent_bridge import get_roster
from backend.simulation.agents import AgentTask, IncidentPlan, build_pipeline, verify_plan
from backend.simulation.engine import SimulationEngine
from backend.simulation.models import (
    AlarmSeverity,
    Incident,
    IncidentStatus,
    Plant,
    SimulationEvent,
)
from backend.simulation.persistence import SimulationStore, get_store
from backend.simulation.response import (
    build_user_summary,
    choose_failover,
    failover_candidates,
    maintenance_counts,
    predict_next_failure,
    resolve_department,
)

logger = logging.getLogger(__name__)

QUEUE_MAXSIZE = 512


#: Canonical event aliases. The engine's internal names are kept (existing
#: subscribers depend on them) and the spec's names are emitted alongside, so
#: the documented contract in docs/simulation/SIMULATION_INTEGRATION.md and the
#: stream actually agree.
EVENT_ALIASES: dict[str, str] = {
    "fault.injected": "simulation.fault",
    "telemetry.batch": "telemetry.updated",
    "agent.task_started": "agent.task.created",
    "agent.tool_completed": "agent.tool.called",
    "agent.evidence_found": "agent.progress",
    "agent.task_completed": "agent.completed",
    "approval.required": "approval.requested",
    "audit.recorded": "audit.created",
}


class PlantRuntime:
    """Everything a running plant accumulates."""

    def __init__(self, engine: SimulationEngine) -> None:
        self.engine = engine
        self.running = False
        self.seq = 0
        self.events: list[SimulationEvent] = []  # durable replay log
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.incident_tasks: dict[str, list[AgentTask]] = {}
        self.incident_plans: dict[str, IncidentPlan] = {}
        self.pending_approval: dict[str, str] = {}  # incident_id -> plan json
        self.artifacts: list[dict] = []

    def emit(self, type_: str, payload: dict, at: float | None = None) -> SimulationEvent:
        self.seq += 1
        # `at` is the sim-time the event describes; it defaults to the current
        # engine clock. Callers that emit a record for a pipeline step pass the
        # step's own timestamp so the console shows the event's real time rather
        # than the time the request happened to flush.
        ev = SimulationEvent(
            seq=self.seq, plant_id=self.engine.plant.id, type=type_, payload=payload,
            at=self.engine.t if at is None else at,
        )
        self.events.append(ev)
        if len(self.events) > 5000:
            del self.events[:2500]
        frame = ev.model_dump()
        alias = EVENT_ALIASES.get(type_)
        if alias:
            frame["alias"] = alias
        for q in list(self.subscribers):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                self.subscribers.discard(q)  # drop slow subscriber, per bus doctrine
        return ev


class SimulationService:
    """Facade used by the API layer. Plants register their datasets here."""

    def __init__(self, store: SimulationStore | None = None) -> None:
        self._plants: dict[str, PlantRuntime] = {}
        self._tick_tasks: dict[str, asyncio.Task] = {}
        #: Durable source of truth. The runtime dictionaries are a cache of
        #: what is already on disk, never the other way around.
        self.store = store or get_store()
        self.roster = get_roster()
        #: Telemetry is high-volume; persist every Nth tick to keep the write
        #: path bounded while still giving a queryable history.
        self.telemetry_every = 1
        self._tick_count: dict[str, int] = {}

    # ------------------------------------------------------------ lifecycle

    def register(self, plant: Plant, seed: int = 117, origin: str = "dataset") -> PlantRuntime:
        rt = PlantRuntime(SimulationEngine(plant, seed=seed))
        self._plants[plant.id] = rt
        # Persist the whole plant graph up front: plants, zones, equipment,
        # sensors, actuators, connections. Incident foreign keys resolve only
        # because this ran.
        self.store.save_plant(plant, origin=origin)
        self.store.audit(
            event_type="plant.registered", actor="system", plant_id=plant.id,
            target=plant.id, result=f"{len(plant.equipment)} equipment",
            runtime=self.roster.runtime_label(),
        )
        return rt

    def registered_ids(self) -> list[str]:
        """Plants currently running in this process (the DB knows more)."""
        return sorted(self._plants)

    def runtime(self, plant_id: str) -> PlantRuntime:
        if plant_id not in self._plants:
            raise KeyError(f"plant {plant_id} not registered")
        return self._plants[plant_id]

    def start(self, plant_id: str) -> None:
        rt = self.runtime(plant_id)
        rt.running = True
        rt.emit("simulation.started", {"plant": plant_id})
        self.store.audit(event_type="simulation.started", actor="operator", plant_id=plant_id,
                         sim_t=rt.engine.t)

    def pause(self, plant_id: str) -> None:
        rt = self.runtime(plant_id)
        rt.running = False
        rt.emit("simulation.paused", {"plant": plant_id})

    def reset(self, plant_id: str, plant: Plant, seed: int = 117) -> PlantRuntime:
        """Discard the running plant and rebuild it from the pristine dataset.

        Operator mutations live only in the runtime, so dropping the runtime is
        what makes a reload genuinely restore normal. The stale runtime's
        measurement-loss incidents are closed first: the store has no delete
        API, and leaving them open would contradict the reset."""
        old = self._plants.pop(plant_id, None)
        if old is not None:
            self._close_sensor_incidents(old)
        rt = self.register(plant, seed=seed)
        self.store.audit(
            event_type="plant.reset", actor="operator", plant_id=plant_id, target=plant_id,
            sim_t=rt.engine.t, result=f"{len(plant.equipment)} equipment",
            runtime=self.roster.runtime_label(),
        )
        return rt

    # ----------------------------------------------------------------- tick

    def step(self, plant_id: str) -> dict:
        """One synchronous tick — the unit-testable heart of the loop."""
        rt = self.runtime(plant_id)
        frame = rt.engine.tick()
        n = self._tick_count.get(plant_id, 0) + 1
        self._tick_count[plant_id] = n
        written = 0
        if self.telemetry_every and n % self.telemetry_every == 0:
            written = self.store.record_telemetry(plant_id, frame["readings"], frame["t"])
        rt.emit("telemetry.batch", {
            "t": frame["t"], "count": len(frame["readings"]),
            "persisted": written, "readings": frame["readings"],
        })
        for alarm in frame["alarms"]:
            rt.emit("alarm.created", alarm)
            self.store.audit(event_type="alarm.created", actor="engine", plant_id=plant_id,
                             sim_t=frame["t"], target=alarm.get("tag"), result=alarm.get("severity"),
                             payload=alarm)
        return frame

    async def run_loop(self, plant_id: str, tick_s: float = 1.0) -> None:
        rt = self.runtime(plant_id)
        while True:
            await asyncio.sleep(tick_s)
            if rt.running:
                self.step(plant_id)

    # -------------------------------------------------------------- control

    def inject_failure(self, plant_id: str, equipment_id: str, mode_id: str) -> dict:
        """Fault injection → real state change → incident → agent pipeline."""
        rt = self.runtime(plant_id)
        changed = rt.engine.inject_failure(equipment_id, mode_id)
        rt.emit("fault.injected", changed)

        mode = next(m for m in rt.engine.plant.failure_modes if m.id == mode_id)
        fault_id = f"FLT-{plant_id}-{equipment_id}-{mode_id}-{rt.seq}"
        self.store.record_fault(
            fault_id, plant_id, equipment_id, changed.get("sensor_id"),
            mode_id, mode.mechanism, changed, rt.engine.t,
        )
        self.store.audit(
            event_type="simulation.fault", actor="operator", plant_id=plant_id,
            sim_t=rt.engine.t, action="inject_failure", target=equipment_id,
            result=mode.mechanism, payload={"fault_event_id": fault_id, **changed},
        )
        eq = next(e for e in rt.engine.plant.equipment if e.id == equipment_id)
        severity = AlarmSeverity.CRITICAL if mode.mechanism in ("stop", "leak") else AlarmSeverity.WARNING
        title = f"{changed.get('tag', eq.tag)} — {mode.name}"
        incident = rt.engine.create_incident(
            title=title,
            severity=severity,
            origin_equipment=equipment_id,
            origin_sensor=changed.get("sensor_id"),
            failure_mode=mode_id,
        )
        self.store.upsert_incident(incident, fault_event_id=fault_id)
        rt.emit("incident.created", incident.model_dump())
        self._emit_perception(rt, incident, source="fault.injected")
        self.store.audit(
            event_type="incident.created", actor="orchestrator", plant_id=plant_id,
            incident_id=incident.id, sim_t=rt.engine.t, target=equipment_id,
            result=incident.severity.value, runtime=self.roster.runtime_label(),
            payload={"affected": incident.affected},
        )
        self._run_agents(rt, incident)
        return {"changed": changed, "incident": incident.model_dump(), "fault_event_id": fault_id}

    def disable_equipment(self, plant_id: str, equipment_id: str) -> None:
        rt = self.runtime(plant_id)
        rt.engine.disable_equipment(equipment_id)
        rt.emit("equipment.disabled", {"equipment_id": equipment_id})

    def remove_equipment(self, plant_id: str, equipment_id: str) -> list[str]:
        rt = self.runtime(plant_id)
        affected = rt.engine.remove_equipment(equipment_id)
        rt.emit("equipment.removed", {"equipment_id": equipment_id, "broken_paths": affected})
        return affected

    # --------------------------------------------------------------- sensors

    def disable_sensor(self, plant_id: str, sensor_id: str) -> dict:
        """Take a sensor out of service, then put the agents on the resulting
        measurement loss — a dead transmitter is an anomaly, not a config edit."""
        rt = self.runtime(plant_id)
        context = self._sensor_redundancy(rt.engine, sensor_id)
        rt.engine.disable_sensor(sensor_id)
        rt.emit("sensor.disabled", {"sensor_id": sensor_id})
        self.store.audit(event_type="sensor.disabled", actor="operator", plant_id=plant_id,
                         sim_t=rt.engine.t, action="disable_sensor", target=sensor_id)
        tag = rt.engine.sensor_model[sensor_id].tag
        incident_id = self._raise_sensor_incident(
            rt, sensor_id, AlarmSeverity.WARNING, f"Loss of measurement — {tag}",
        )
        return {**context, "incident_id": incident_id}

    def remove_sensor(self, plant_id: str, sensor_id: str) -> dict:
        """Delete a sensor outright and engage the agents on the loss.

        Redundancy is read *before* the point leaves the running plant: the
        console renders what still covers the measurement."""
        rt = self.runtime(plant_id)
        context = self._sensor_redundancy(rt.engine, sensor_id)
        rt.engine.remove_sensor(sensor_id)
        rt.emit("sensor.removed", {"sensor_id": sensor_id})
        self.store.audit(event_type="sensor.removed", actor="operator", plant_id=plant_id,
                         sim_t=rt.engine.t, action="remove_sensor", target=sensor_id,
                         payload=context)
        tag = rt.engine.sensor_model[sensor_id].tag
        incident_id = self._raise_sensor_incident(
            rt, sensor_id, AlarmSeverity.CRITICAL, f"Instrument deleted — {tag}",
        )
        return {**context, "incident_id": incident_id}

    def restore_sensor(self, plant_id: str, sensor_id: str) -> None:
        rt = self.runtime(plant_id)
        rt.engine.restore_sensor(sensor_id)
        rt.emit("sensor.restored", {"sensor_id": sensor_id})
        self.store.audit(event_type="sensor.restored", actor="operator", plant_id=plant_id,
                         sim_t=rt.engine.t, action="restore_sensor", target=sensor_id)

    def _sensor_redundancy(self, engine: SimulationEngine, sensor_id: str) -> dict:
        """What still reads a point the operator is removing.

        Reuses ``engine.alternate_sensors`` — the same reasoning the agent
        pipeline uses — and keeps only points that can actually read, so the UI
        never offers a substitute that is itself dead."""
        model = engine.sensor_model[sensor_id]  # KeyError → 404 at the API
        alternates = [
            s.id for s in engine.alternate_sensors(sensor_id)
            if s.id in engine.sensors
            and engine.sensor_out_of_service(s.id) is None
            and not engine.sensors[s.id].failed
        ]
        return {
            "sensor_id": sensor_id,
            "equipment_id": model.equipment_id,
            "measurement": model.measurement.value,
            "alternates": alternates,
            "affected": engine.neighbors(model.equipment_id, depth=2)["affected"],
        }

    def _open_sensor_incident(self, rt: PlantRuntime, sensor_id: str) -> Incident | None:
        """A not-yet-resolved incident already tracking this sensor.

        Re-raising would stack a second task DAG and a second approval on the
        same loss, so the console would show the agents twice."""
        return next(
            (i for i in rt.engine.incidents.values()
             if i.origin_sensor == sensor_id and i.status != IncidentStatus.RESOLVED),
            None,
        )

    def _raise_sensor_incident(self, rt: PlantRuntime, sensor_id: str, severity: AlarmSeverity,
                               title: str) -> str | None:
        """Raise the measurement-loss incident and run the real agent pipeline.

        Same machinery as ``inject_failure`` (create_incident → store → event →
        ``_run_agents``); an open incident for the same point is reused instead
        of duplicated."""
        existing = self._open_sensor_incident(rt, sensor_id)
        if existing is not None:
            return existing.id
        model = rt.engine.sensor_model[sensor_id]
        incident = rt.engine.create_incident(
            title=title,
            severity=severity,
            origin_equipment=model.equipment_id,
            origin_sensor=sensor_id,
            failure_mode=None,
        )
        self.store.upsert_incident(incident)
        rt.emit("incident.created", incident.model_dump())
        self._emit_perception(rt, incident, source="sensor.loss")
        self.store.audit(
            event_type="incident.created", actor="orchestrator", plant_id=rt.engine.plant.id,
            incident_id=incident.id, sim_t=rt.engine.t, target=model.equipment_id,
            result=incident.severity.value, runtime=self.roster.runtime_label(),
            payload={"affected": incident.affected, "origin_sensor": sensor_id},
        )
        self._run_agents(rt, incident)
        return incident.id

    def _close_sensor_incidents(self, rt: PlantRuntime) -> None:
        """Resolve measurement-loss incidents before their runtime is dropped."""
        for incident in rt.engine.incidents.values():
            if incident.origin_sensor is None or incident.status == IncidentStatus.RESOLVED:
                continue
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = rt.engine.t
            self.store.upsert_incident(incident)

    # --------------------------------------------------------- agent pipeline

    def _emit_perception(self, rt: PlantRuntime, incident: Incident, source: str) -> None:
        """Lane A's opening event, emitted the moment an incident exists.

        WHY a dedicated event instead of overloading ``fault.injected``: the
        incident id is only known after ``create_incident`` runs, and the
        console buckets every beat by that job id. The perception beat carries
        the tag, declared fault, severity and department the console shows, so
        lane A never has to guess or wait for the slower agent.started event.
        """
        engine = rt.engine
        eq = next((e for e in engine.plant.equipment if e.id == incident.origin_equipment), None)
        mode = next((m for m in engine.plant.failure_modes if m.id == incident.failure_mode), None)
        sensor = engine.sensor_model.get(incident.origin_sensor) if incident.origin_sensor else None
        department = resolve_department(engine, incident.origin_equipment)
        rt.emit("response.perception", {
            "job_id": incident.id,
            "incident_id": incident.id,
            "equipment_id": incident.origin_equipment,
            "equipment_tag": eq.tag if eq else incident.origin_equipment,
            "fault_type": incident.failure_mode,
            "fault_name": mode.name if mode else None,
            "mechanism": mode.mechanism if mode else None,
            "severity": incident.severity.value,
            "sensor_id": sensor.id if sensor else None,
            "sensor_tag": sensor.tag if sensor else None,
            "department": department["department"],
            "department_source": department["department_source"],
            "source": source,
        })

    def _emit_response_lanes(self, rt: PlantRuntime, incident: Incident,
                             tasks: list[AgentTask]) -> None:
        """Emit the parallel operations + diagnostics lane beats.

        WHY these beats exist: the console's lane checklists require facts the
        task/tool stream cannot express (department notified, the alternate the
        engine actually chose, maintenance counts, the closing user summary).
        Every field is derived from engine state or the pipeline's own evidence
        by ``response.py`` — none is scripted.

        Operations (lane B) and diagnostics (lane C) are dispatched together at
        handoff, so both ``response.lane_started`` events are emitted back to
        back before any lane beat. That is what makes the two lanes concurrent
        in the console rather than sequentially ordered.
        """
        engine = rt.engine
        eq = next((e for e in engine.plant.equipment if e.id == incident.origin_equipment), None)
        equipment_tag = eq.tag if eq else incident.origin_equipment
        department = resolve_department(engine, incident.origin_equipment)
        job = {
            "job_id": incident.id,
            "incident_id": incident.id,
            "equipment_id": incident.origin_equipment,
            "equipment_tag": equipment_tag,
            "department": department["department"],
            "department_source": department["department_source"],
        }

        rt.emit("response.lane_started", {**job, "lane": "operations"})
        rt.emit("response.lane_started", {**job, "lane": "diagnostics"})

        # --- lane B, operations continuity / failover -----------------------
        rt.emit("response.operations_notified", {**job, "role": "shift supervisor"})

        origin_sensor = incident.origin_sensor
        rt.emit("response.failover_evaluating", {
            **job,
            "origin_sensor_id": origin_sensor,
            "candidates": failover_candidates(engine, origin_sensor),
        })
        chosen = choose_failover(engine, origin_sensor)
        if chosen is not None:
            origin_equipment = engine.sensor_model[origin_sensor].equipment_id if origin_sensor else None
            rt.emit("response.failover_completed", {
                **job,
                "origin_sensor_id": origin_sensor,
                "related_equipment_id": chosen.equipment_id,
                "related_sensor_id": chosen.id,
                "related_sensor_tag": chosen.tag,
                "same_asset": chosen.equipment_id == origin_equipment,
            })
        # No usable alternate -> this beat is never emitted. The console reports
        # "no response from orchestrator" after the configured timeout instead
        # of inventing a switch.

        # --- lane C, diagnostics -------------------------------------------
        rt.emit("response.history_reviewed", {
            **job,
            "counts": maintenance_counts(engine, incident, tasks),
        })

        mode = next((m for m in engine.plant.failure_modes if m.id == incident.failure_mode), None)
        sensor = engine.sensor_model.get(origin_sensor) if origin_sensor else None
        if mode is not None and eq is not None and mode.id in eq.failure_modes:
            explanation = mode.description or f"{equipment_tag}: {mode.name} confirmed by the evidence pack."
        elif sensor is not None:
            explanation = (
                f"{sensor.tag} measurement loss on {equipment_tag} — no declared equipment "
                "failure mode recorded."
            )
        else:
            explanation = f"{equipment_tag}: fault confirmed by the evidence pack."
        rt.emit("response.root_cause_identified", {
            **job,
            # A failure mode is only reported when the equipment itself declares
            # it; sensor-loss incidents honestly report no mode.
            "failure_mode": mode.id if mode is not None else None,
            "failure_mode_name": mode.name if mode is not None else None,
            "mechanism": mode.mechanism if mode is not None else None,
            "failure_mode_declared": bool(mode is not None and eq is not None and mode.id in eq.failure_modes),
            "explanation": explanation,
        })

        prediction = predict_next_failure(engine, incident)
        rt.emit("response.prediction", {**job, **prediction})
        rt.emit("response.user_notified", {
            **job,
            "summary": build_user_summary(equipment_tag, mode, chosen, prediction),
        })

    def _run_agents(self, rt: PlantRuntime, incident: Incident) -> None:
        """Execute the deterministic multi-agent pipeline, emitting the events
        the Command Center renders. Timestamps come from sim time advanced by
        the pipeline — never invented."""
        incident.status = IncidentStatus.INVESTIGATING
        self.store.upsert_incident(incident)
        rt.emit("incident.updated", incident.model_dump())

        execution_id = f"EXEC-{incident.id}"
        runtime_label = self.roster.runtime_label()
        self.store.start_execution(execution_id, incident.id, incident.plant_id, runtime_label)
        eq = next((e for e in rt.engine.plant.equipment if e.id == incident.origin_equipment), None)
        mode = next((m for m in rt.engine.plant.failure_modes if m.id == incident.failure_mode), None)
        department = resolve_department(rt.engine, incident.origin_equipment)
        handoff = {
            "from": "perception",
            "to": ["operations", "diagnostics"],
            "equipment_id": incident.origin_equipment,
            "equipment_tag": eq.tag if eq else incident.origin_equipment,
        }
        rt.emit("agent.started", {
            "execution_id": execution_id, "incident_id": incident.id,
            "runtime": runtime_label, "agents": self.roster.status()["roles"],
            # Console-facing context: the same real incident fields the lanes
            # key off, plus the explicit handoff that tells lane A it may grey.
            "job_id": incident.id,
            "equipment_id": incident.origin_equipment,
            "equipment_tag": eq.tag if eq else incident.origin_equipment,
            "fault_type": incident.failure_mode,
            "fault_name": mode.name if mode else None,
            "severity": incident.severity.value,
            "department": department["department"],
            "handoff": handoff,
        })
        self.store.audit(event_type="agent.started", actor="orchestrator", plant_id=incident.plant_id,
                         incident_id=incident.id, sim_t=rt.engine.t, runtime=runtime_label,
                         payload=self.roster.status())

        tasks, plan = build_pipeline(rt.engine, incident, rt.engine.t)
        rt.incident_tasks[incident.id] = tasks
        rt.incident_plans[incident.id] = plan
        rt.pending_approval[incident.id] = plan.model_dump_json()

        # The lane beats are emitted at handoff, before the per-task record
        # loop, because the pipeline has already dispatched every specialist
        # agent by this point.
        self._emit_response_lanes(rt, incident, tasks)

        for task in tasks:
            rt.emit("agent.task_started", task.model_dump())
            self.store.upsert_task(execution_id, task)
            self.store.audit(event_type="agent.task.created", actor=task.agent,
                             plant_id=incident.plant_id, incident_id=incident.id,
                             task_id=task.id, sim_t=task.started_at, runtime=task.agent_runtime,
                             result=task.status)
            for tool in task.tools:
                rt.emit("agent.tool_completed", {"task_id": task.id, "tool": tool.tool, "summary": tool.summary, "ok": tool.ok})
                self.store.audit(event_type="agent.tool.called", actor=task.agent,
                                 plant_id=incident.plant_id, incident_id=incident.id,
                                 task_id=task.id, action=tool.tool,
                                 result="ok" if tool.ok else "failed",
                                 runtime=task.agent_runtime, payload={"summary": tool.summary})
            for ev in task.evidence:
                rt.emit("agent.evidence_found", ev.model_dump())
                self.store.add_evidence(task.id, incident.id, ev)
            # A task the pipeline could not complete (e.g. retrieval found
            # nothing) stays blocked — it is never upgraded to completed.
            if task.status != "blocked":
                task.status = "completed"
            rt.emit("agent.task_completed", task.model_dump())
            self.store.upsert_task(execution_id, task)
            self.store.audit(event_type="agent.completed", actor=task.agent,
                             plant_id=incident.plant_id, incident_id=incident.id,
                             task_id=task.id, sim_t=task.completed_at,
                             result=task.status, evidence_count=len(task.evidence),
                             runtime=task.agent_runtime,
                             payload={"agent_error": task.agent_error} if task.agent_error else None)

        blocked = [t.id for t in tasks if t.status == "blocked"]
        self.store.finish_execution(execution_id, "blocked" if blocked else "completed", len(tasks))

        approval_id = f"APR-{incident.id}"
        self.store.request_approval(approval_id, incident.id, plan.approval_reason, plan.model_dump())
        incident.status = IncidentStatus.AWAITING_APPROVAL
        self.store.upsert_incident(incident)
        rt.emit("incident.updated", incident.model_dump())
        rt.emit("approval.required", {
            "incident_id": incident.id,
            "approval_id": approval_id,
            "action": plan.action,
            "reason": plan.approval_reason,
            "steps": plan.steps,
            "risk": "medium",
            "blocked_tasks": blocked,
        })
        self.store.audit(event_type="approval.requested", actor="orchestrator",
                         plant_id=incident.plant_id, incident_id=incident.id,
                         approval_id=approval_id, action=plan.action.get("kind"),
                         target=plan.action.get("target"), sim_t=rt.engine.t,
                         runtime=runtime_label)

    def decide(self, plant_id: str, incident_id: str, approved: bool) -> dict:
        """Human decision → action → verification → resolution."""
        rt = self.runtime(plant_id)
        incident = rt.engine.incidents[incident_id]
        plan = rt.incident_plans[incident_id]
        approval_id = f"APR-{incident_id}"
        self.store.decide_approval(approval_id, approved)
        rt.emit("approval.granted" if approved else "approval.rejected",
                {"incident_id": incident_id, "approval_id": approval_id})
        self.store.audit(event_type="approval.granted" if approved else "approval.rejected",
                         actor="operator", plant_id=plant_id, incident_id=incident_id,
                         approval_id=approval_id, sim_t=rt.engine.t)
        if not approved:
            incident.status = IncidentStatus.ESCALATED
            self.store.upsert_incident(incident)
            rt.emit("incident.updated", incident.model_dump())
            return {"status": incident.status.value}

        incident.status = IncidentStatus.ACTING
        self.store.upsert_incident(incident)
        rt.emit("incident.updated", incident.model_dump())

        # Policy gate → executor. A blocked or failed action never reaches
        # verification and never reports success.
        action_id = f"ACT-{incident_id}"
        outcome = execute_action(rt.engine, incident, plan.action, job_id=incident_id)
        self.store.start_action(action_id, incident_id, approval_id, plan.action["kind"],
                                str(plan.action.get("target")), outcome.executor,
                                outcome.policy, outcome.policy_reason)
        rt.emit("action.started", {"incident_id": incident_id, "action_id": action_id,
                                   "kind": plan.action["kind"], "executor": outcome.executor,
                                   "policy": outcome.policy})
        self.store.audit(event_type="action.started", actor="orchestrator", plant_id=plant_id,
                         incident_id=incident_id, approval_id=approval_id,
                         action=plan.action["kind"], target=str(plan.action.get("target")),
                         result=outcome.executor, sim_t=rt.engine.t,
                         payload={"policy": outcome.policy, "policy_reason": outcome.policy_reason})
        self.store.finish_action(action_id, outcome.status, outcome.detail)
        self.store.audit(event_type="action.completed" if outcome.ok else "action.blocked",
                         actor="orchestrator", plant_id=plant_id, incident_id=incident_id,
                         approval_id=approval_id, action=plan.action["kind"],
                         target=str(plan.action.get("target")), result=outcome.status,
                         sim_t=rt.engine.t, payload=outcome.detail)
        if not outcome.ok:
            incident.status = IncidentStatus.ESCALATED
            self.store.upsert_incident(incident)
            rt.emit("action.blocked", {"incident_id": incident_id, "action_id": action_id,
                                        **outcome.detail})
            rt.emit("incident.updated", incident.model_dump())
            return {
                "status": incident.status.value, "verified": False,
                "action": outcome.status, "policy": outcome.policy,
                "findings": [outcome.detail.get("message", "action did not execute")],
            }
        result = dict(outcome.detail)
        rt.emit("action.completed", {"action_id": action_id, **result})

        incident.status = IncidentStatus.VERIFYING
        self.store.upsert_incident(incident)
        rt.emit("verification.started", {"incident_id": incident_id, "action_id": action_id})
        self.store.audit(event_type="verification.started", actor="orchestrator",
                         plant_id=plant_id, incident_id=incident_id, sim_t=rt.engine.t)
        # Observe until the plant settles — bounded at 12 ticks. Verification
        # is real each pass; if the envelope never recovers the incident stays
        # open and the caller sees verified=False.
        ok, findings = False, []
        checks = 0
        for _ in range(12):
            self.step(plant_id)
            checks += 1
            ok, findings = verify_plan(rt.engine, incident)
            if ok:
                break
        verification_id = f"VER-{incident_id}"
        self.store.record_verification(verification_id, incident_id, action_id, ok, findings,
                                        checks, rt.engine.t)
        rt.emit("verification.completed", {"incident_id": incident_id, "ok": ok,
                                            "findings": findings, "checks_run": checks,
                                            "verification_id": verification_id})
        self.store.audit(event_type="verification.completed", actor="orchestrator",
                         plant_id=plant_id, incident_id=incident_id,
                         verification_id=verification_id, result="passed" if ok else "failed",
                         sim_t=rt.engine.t, payload={"findings": findings, "checks_run": checks})

        if ok:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = rt.engine.t
            artifact = {
                "id": f"ART-{incident.id}",
                "kind": "incident_report",
                "filename": f"incident_{incident.id.lower()}.pdf",
                "verified": True,
                "sources": len(rt.incident_tasks.get(incident_id, [])),
                "created_at": rt.engine.t,
            }
            artifact["body"] = self._artifact_body(rt, incident, result, findings)
            rt.artifacts.append(artifact)
            self.store.record_artifact(artifact, incident_id)
            self.store.upsert_incident(incident)
            rt.emit("artifact.created", artifact)
            self.store.audit(event_type="artifact.created", actor="documentation",
                             plant_id=plant_id, incident_id=incident_id,
                             action="artifact.created", target=artifact["filename"],
                             result="verified", sim_t=rt.engine.t,
                             payload={"artifact_id": artifact["id"], "sources": artifact["sources"]})
            rt.emit("incident.resolved", incident.model_dump())
            audit_id = self.store.audit(
                event_type="incident.resolved", actor="operator", plant_id=plant_id,
                incident_id=incident_id, sim_t=rt.engine.t, action="incident.resolved",
                verification_id=verification_id, approval_id=approval_id,
                target=str(plan.action.get("target")), result="resolved",
                evidence_count=sum(len(t.evidence) for t in rt.incident_tasks.get(incident_id, [])),
                runtime=self.roster.runtime_label(),
            )
            rt.emit("audit.recorded", {"incident_id": incident_id, "actor": "operator",
                                        "action": "incident.resolved", "audit_id": audit_id,
                                        "persisted": True})
        else:
            incident.status = IncidentStatus.INVESTIGATING  # verification failed → orchestrator continues
            self.store.upsert_incident(incident)
            rt.emit("incident.updated", incident.model_dump())
        return {"status": incident.status.value, "verified": ok, "findings": findings,
                "action": outcome.status, "verification_id": verification_id}

    def _artifact_body(self, rt: PlantRuntime, incident: Incident, action: dict,
                       findings: list[str]) -> str:
        """Incident report text assembled from the persisted records."""
        tasks = rt.incident_tasks.get(incident.id, [])
        lines = [
            f"# Incident {incident.id} — {incident.title}",
            f"Plant: {incident.plant_id} · severity: {incident.severity.value}",
            f"Origin: {incident.origin_equipment} · affected: {len(incident.affected)}",
            "",
            "## Agent tasks",
        ]
        for t in tasks:
            lines.append(
                f"- [{t.status}] {t.agent}: {t.title} — {len(t.evidence)} evidence, "
                f"tools: {', '.join(tc.tool for tc in t.tools) or 'none'} (runtime {t.agent_runtime})"
            )
        cites = [e.citation for t in tasks for e in t.evidence if e.citation]
        lines += ["", "## Citations"]
        lines += [f"- {c}" for c in cites] or ["- none"]
        lines += ["", "## Action", f"- {action}", "", "## Verification"]
        lines += [f"- {f}" for f in findings] or ["- no findings recorded"]
        return "\n".join(lines)

    # ------------------------------------------------------------- streaming

    async def subscribe(self, plant_id: str, after_seq: int = 0) -> AsyncIterator[dict]:
        """Replay durable log from `after_seq`, then follow the live bus."""
        rt = self.runtime(plant_id)
        for ev in rt.events:
            if ev.seq > after_seq:
                yield ev.model_dump()
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        rt.subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            rt.subscribers.discard(q)


#: Process-wide service — the one place engine instances live.
simulation_service = SimulationService()
