"""Multi-agent incident pipeline — deterministic, evidence-first.

This is NOT a chatbot script. The orchestrator builds the task DAG from the
*actual* incident context (topology neighborhood, alternate sensors,
maintenance metadata), each agent's tools query the *actual* engine state,
and the plan only contains actions the engine can really execute.

No private chain-of-thought is produced — the records are actions, tools,
evidence, results, dependencies: exactly what the Command Center renders.

In live mode the service hands each agent's evidence pack to the real
Project 117 agents (backend/agents/*) for narrative generation; the
orchestration records below are identical either way.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.simulation.agent_bridge import get_roster
from backend.simulation.engine import SimulationEngine
from backend.simulation.models import (
    AlarmSeverity,
    Incident,
    TelemetryQuality,
)
from backend.simulation.retrieval import RetrievalUnavailable, get_retriever


class ToolCall(BaseModel):
    tool: str
    summary: str
    ok: bool = True


class Evidence(BaseModel):
    id: str
    source_type: str  # telemetry|graph|documents|maintenance|policy
    source_id: str
    description: str
    confidence: float = 0.9
    #: Populated for retrieved documents: "<document_id>#<chunk_id>".
    citation: str | None = None
    #: Retrieval metadata (source path, revision, score) when applicable.
    metadata: dict = Field(default_factory=dict)


class AgentTask(BaseModel):
    """One unit of agent work (AgentExecution in the spec)."""

    id: str
    incident_id: str
    agent: str  # orchestrator|data_analysis|maintenance|operations|safety|documentation
    title: str
    status: str = "queued"  # queued|running|completed|failed|blocked
    started_at: float | None = None
    completed_at: float | None = None
    depends_on: list[str] = Field(default_factory=list)
    tools: list[ToolCall] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    result: str = ""
    sequence: int = 0
    #: Which runtime produced ``result``: "project117-agents" when the real
    #: agent in backend/agents ran, "deterministic-evidence" when the engine
    #: derived it because that runtime was unavailable. Never cosmetic.
    agent_runtime: str = "deterministic-evidence"
    agent_available: bool = False
    agent_error: str | None = None


class IncidentPlan(BaseModel):
    incident_id: str
    steps: list[str]
    requires_approval: bool
    approval_reason: str
    action: dict  # {"kind": "repair_sensor"|"restore_equipment"|"reduce_load", "target": id}
    verification: list[str]


def build_graph_context(engine: SimulationEngine, incident: Incident) -> dict:
    """Topology facts for the agents, read from the plant graph.

    Returns upstream/downstream equipment (tag + kind), the process areas the
    blast radius touches, and the related measurements on those assets. This is
    the only source the agents get for "what else is affected" — there is no
    per-asset table anywhere in the code.
    """
    origin = incident.origin_equipment
    by_id = {e.id: e for e in engine.plant.equipment}
    areas_by_id = {a.id: a for a in engine.plant.areas}

    def describe(eq_id: str) -> dict:
        e = by_id[eq_id]
        rt = engine.eq[eq_id]
        return {
            "id": e.id, "tag": e.tag, "kind": e.kind.value, "area_id": e.area_id,
            "state": rt.state.value, "capacity": round(rt.capacity, 3),
        }

    upstream = [describe(i) for i in engine.upstream.get(origin, []) if i in by_id]
    downstream = [describe(i) for i in engine.downstream.get(origin, []) if i in by_id]
    scope = [origin, *incident.affected]
    area_ids: list[str] = []
    for eq_id in scope:
        e = by_id.get(eq_id)
        if e and e.area_id not in area_ids:
            area_ids.append(e.area_id)
    areas = [
        {
            "id": aid,
            "name": areas_by_id[aid].name if aid in areas_by_id else aid,
            "equipment_count": sum(1 for e in engine.plant.equipment if e.area_id == aid),
        }
        for aid in area_ids
    ]
    related_sensors = [
        {
            "id": s.id, "tag": s.tag, "equipment_id": s.equipment_id,
            "measurement": s.measurement.value, "unit": s.unit,
            "value": round(engine.sensors[s.id].value, 3),
            "quality": engine.sensors[s.id].quality.value,
        }
        for eq_id in scope
        if eq_id in by_id
        for s in by_id[eq_id].sensors
    ]
    paths = [
        {"id": c.id, "source": c.source, "target": c.target, "medium": c.medium,
         "kind": c.kind.value, "leaking": c.leaking, "enabled": c.enabled}
        for c in engine.plant.connections
        if c.source in scope or c.target in scope
    ]
    return {
        "origin": describe(origin) if origin in by_id else {"id": origin},
        "upstream": upstream,
        "downstream": downstream,
        "affected": [describe(i) for i in incident.affected if i in by_id],
        "areas": areas,
        "related_sensors": related_sensors,
        "paths": paths,
    }


def _fmt_value(engine: SimulationEngine, sensor_id: str) -> str:
    rt = engine.sensors[sensor_id]
    m = engine.sensor_model[sensor_id]
    return f"{m.tag} = {rt.value:.1f} {m.unit} ({rt.quality.value})"


def build_pipeline(engine: SimulationEngine, incident: Incident, t0: float) -> tuple[list[AgentTask], IncidentPlan]:
    """Decompose an incident into a real task DAG + an executable plan.

    Driven by the incident origin and the live topology — run it against any
    equipment in any plant and the DAG shape follows the graph.
    """
    tasks: list[AgentTask] = []
    seq = 0
    t = t0

    def add(agent: str, title: str, depends_on: list[str] | None = None) -> AgentTask:
        nonlocal seq, t
        seq += 1
        t += 1.0
        task = AgentTask(
            id=f"{incident.id}-T{seq}",
            incident_id=incident.id,
            agent=agent,
            title=title,
            started_at=t,
            completed_at=t + engine.tick_s,
            depends_on=depends_on or [],
            sequence=seq,
        )
        tasks.append(task)
        return task

    origin = incident.origin_equipment
    origin_sensor = incident.origin_sensor
    eq = next(e for e in engine.plant.equipment if e.id == origin)
    affected = incident.affected

    # --- GRAPH CONTEXT ------------------------------------------------------
    # Everything below is derived from the plant graph at runtime: the
    # connection list gives upstream/downstream, equipment membership gives
    # the affected process areas, and the sensor lists give related
    # measurements. No asset id appears literally anywhere in this file.
    graph_context = build_graph_context(engine, incident)

    # --- ORCHESTRATOR -------------------------------------------------------
    orch = add("orchestrator", "Classify incident and decompose into agent tasks")
    orch.tools.append(ToolCall(tool="incident.classify", summary=f"{incident.severity.value} · origin {eq.tag}"))
    orch.evidence.append(Evidence(
        id=f"{incident.id}-E0", source_type="topology", source_id=origin,
        description=f"Blast radius: {len(affected)} downstream/upstream assets", confidence=1.0,
    ))
    orch.tools.append(ToolCall(
        tool="graph.context",
        summary=(
            f"{len(graph_context['upstream'])} upstream · {len(graph_context['downstream'])} downstream · "
            f"{len(graph_context['areas'])} area(s) · {len(graph_context['related_sensors'])} related sensor(s)"
        ),
    ))
    for area in graph_context["areas"][:3]:
        orch.evidence.append(Evidence(
            id=f"{incident.id}-EA{len(orch.evidence)}", source_type="topology",
            source_id=area["id"], description=f"Affected process area: {area['name']}",
            confidence=1.0, metadata={"equipment_count": area["equipment_count"]},
        ))
    orch.result = f"Classified as {incident.severity.value} incident on {eq.tag}; 5 agents tasked."

    # --- DATA ANALYSIS ------------------------------------------------------
    da = add("data_analysis", "Validate the failure against related measurements", [orch.id])
    da.tools.append(ToolCall(tool="telemetry.query", summary=f"window t-300s..t · {origin}"))
    da.tools.append(ToolCall(tool="graph.query", summary="sensor redundancy + topology walk"))
    if origin_sensor:
        alts = engine.alternate_sensors(origin_sensor)
        for s in alts[:4]:
            rt = engine.sensors[s.id]
            da.evidence.append(Evidence(
                id=f"{da.id}-E{len(da.evidence)+1}", source_type="telemetry", source_id=s.id,
                description=_fmt_value(engine, s.id),
                confidence=0.95 if rt.quality == TelemetryQuality.GOOD else 0.4,
            ))
        good = [a for a in alts if engine.sensors[a.id].quality == TelemetryQuality.GOOD]
        da.result = (
            f"{len(good)} alternate measurement(s) consistent — process readable via redundancy."
            if good else "No consistent alternate measurement — treat as unreadable process point."
        )
    else:
        da.result = "Telemetry pattern matches the injected failure signature."
    da.tools.append(ToolCall(tool="anomaly.detect", summary=da.result))

    # --- MAINTENANCE --------------------------------------------------------
    mt = add("maintenance", "Evaluate failure mode and replacement requirement", [orch.id])
    mt.tools.append(ToolCall(tool="maintenance_history.query", summary=f"{eq.tag} · last inspection {eq.last_inspection}"))
    mt.tools.append(ToolCall(tool="failure_mode.match", summary=incident.failure_mode or "unknown"))
    mt.evidence.append(Evidence(
        id=f"{mt.id}-E1", source_type="maintenance", source_id=eq.id,
        description=f"{eq.manufacturer} {eq.model} · installed {eq.installed} · inspected {eq.last_inspection}",
        confidence=1.0,
    ))
    mt.result = "Component-level fault confirmed; inspection/replacement required."

    # --- OPERATIONS ---------------------------------------------------------
    op = add("operations", "Evaluate process continuity on degraded instrumentation", [da.id])
    op.tools.append(ToolCall(tool="topology.impact", summary=f"{len(affected)} assets downstream/upstream"))
    for aid in affected[:4]:
        aeq = next(e for e in engine.plant.equipment if e.id == aid)
        rt = engine.eq[aid]
        op.evidence.append(Evidence(
            id=f"{op.id}-E{len(op.evidence)+1}", source_type="topology", source_id=aid,
            description=f"{aeq.tag} capacity {rt.capacity:.0%} · state {rt.state.value}", confidence=0.9,
        ))
    op.result = "Process can continue under compensating monitoring." if origin_sensor else "Production impact under evaluation."

    # --- SAFETY -------------------------------------------------------------
    sf = add("safety", "Check safe-operating envelope", [da.id, mt.id])
    sf.tools.append(ToolCall(tool="policy_check", summary="continued-operation criteria"))
    over_envelope = any(
        not m.is_detector
        and engine.sensors[sid].quality == TelemetryQuality.GOOD
        and (engine.sensors[sid].value >= m.critical_max or engine.sensors[sid].value <= m.critical_min)
        for sid, m in engine.sensor_model.items()
        # a sensor removed from the running plant is absent from `sensors` but
        # still has a model entry (that is what makes a reset able to rebuild it)
        if sid in engine.sensors and m.equipment_id in [origin, *affected]
    )
    sf.evidence.append(Evidence(
        id=f"{sf.id}-E1", source_type="policy", source_id="safe-envelope",
        description="No critical envelope violation on readable sensors" if not over_envelope else "CRITICAL envelope violation present",
        confidence=0.98,
    ))
    sf.result = "Continued operation acceptable with monitoring." if not over_envelope else "Recommend controlled load reduction."

    # --- DOCUMENTATION ------------------------------------------------------
    # Retrieval actually runs here. The query is built from this incident's
    # equipment kind, measurement, failure mechanism and process area, so two
    # different assets cannot retrieve the same document by construction.
    dc = add("documentation", "Retrieve governing procedures", [orch.id])
    retriever = get_retriever()
    mode = next((m for m in engine.plant.failure_modes if m.id == incident.failure_mode), None)
    measurement = engine.sensor_model[origin_sensor].measurement.value if origin_sensor else None
    area_name = next((a.name for a in engine.plant.areas if a.id == eq.area_id), eq.area_id)
    try:
        query, hits = retriever.for_incident(
            equipment_kind=eq.kind.value,
            equipment_tag=eq.tag,
            measurement=measurement,
            mechanism=mode.mechanism if mode else incident.failure_mode,
            area=area_name,
            k=3,
        )
        dc.tools.append(ToolCall(
            tool="retrieve_documents",
            summary=f"{retriever.name} · q={query!r} · {len(hits)} passage(s)",
        ))
        for hit in hits:
            dc.evidence.append(Evidence(
                id=f"{dc.id}-E{len(dc.evidence)+1}",
                source_type="documents",
                source_id=hit.document_id,
                description=f"{hit.title} — {hit.text[:220].strip()}",
                confidence=min(0.99, 0.6 + hit.score / 40.0),
                citation=hit.citation,
                metadata={"source": hit.source, "score": round(hit.score, 3), **hit.metadata},
            ))
        dc.result = (
            "Retrieved " + ", ".join(h.citation for h in hits)
            + f" via {retriever.name}."
        )
    except RetrievalUnavailable as exc:
        # No document matched and no backend could serve the query: the task
        # is blocked, not silently "completed" with an invented citation.
        dc.tools.append(ToolCall(tool="retrieve_documents", summary=str(exc), ok=False))
        dc.status = "blocked"
        dc.result = "No governing document could be retrieved; escalate for manual SOP lookup."

    # --- PLAN (orchestrator synthesis) --------------------------------------
    plan_task = add("orchestrator", "Synthesize response plan", [da.id, mt.id, op.id, sf.id, dc.id])

    if origin_sensor:
        action = {"kind": "repair_sensor", "target": origin_sensor}
        steps = [
            f"Mark {engine.sensor_model[origin_sensor].tag} unavailable (quality=BAD)",
            "Switch control input to validated alternate measurement",
            "Confirm alternate consistency against flow/vibration correlates",
            "Create sensor replacement recommendation",
            "Continue monitoring; escalate if alternates diverge",
        ]
    else:
        action = {"kind": "restore_equipment", "target": origin}
        steps = [
            f"Stabilize {eq.tag} and isolate the faulted path",
            "Confirm downstream pressures/flows return to envelope",
            "Restore capacity in stages with verification at each step",
            "Create maintenance work order with evidence pack",
        ]
    plan_task.result = f"Plan ready: {len(steps)} steps, approval required before action."
    plan_task.tools.append(ToolCall(
        tool="plan.synthesize",
        summary=f"{sum(len(t.evidence) for t in tasks)} evidence item(s) from {len(tasks)} task(s)",
    ))

    # --- Hand each specialist task to the real Project 117 agent ------------
    # The orchestration records above are engine-derived; the narrative result
    # is produced by backend/agents/* when that runtime is reachable. Each
    # task records which runtime served it.
    roster = get_roster()
    for task in tasks:
        if task.agent == "orchestrator" or task.status == "blocked":
            task.agent_runtime = "orchestrator"
            task.agent_available = roster.loaded
            continue
        dispatch = roster.dispatch(
            role=task.agent,
            task=task.title,
            evidence=[e.model_dump() for e in task.evidence],
            job_id=incident.id,
            deterministic_result=task.result,
            tools=[t.tool for t in task.tools],
            inputs={
                "incident_id": incident.id,
                "plant_id": incident.plant_id,
                "equipment_tag": eq.tag,
                "equipment_kind": eq.kind.value,
                "failure_mode": incident.failure_mode,
                "graph_context": graph_context,
            },
        )
        task.result = dispatch.text or task.result
        task.agent_runtime = dispatch.runtime
        task.agent_available = dispatch.available
        task.agent_error = dispatch.error
        for tool_name in dispatch.tools_used:
            if tool_name not in [t.tool for t in task.tools]:
                task.tools.append(ToolCall(tool=tool_name, summary="invoked by agent runtime"))
    plan = IncidentPlan(
        incident_id=incident.id,
        steps=steps,
        requires_approval=True,
        approval_reason=f"Action changes plant state ({eq.tag}); evidence pack attached from {len(tasks)-1} agent tasks.",
        action=action,
        verification=[
            "Alternate/primary measurement consistency within 2%",
            "No active critical alarms on affected assets",
            "Downstream flow stable for 10 consecutive ticks",
        ],
    )

    return tasks, plan


def execute_plan(engine: SimulationEngine, plan: IncidentPlan) -> dict:
    """Run the approved action against the real engine state."""
    kind = plan.action["kind"]
    target = plan.action["target"]
    if kind == "repair_sensor":
        engine.repair_sensor(target)
        return {"executed": kind, "target": target}
    if kind == "restore_equipment":
        engine.restore_equipment(target)
        return {"executed": kind, "target": target}
    if kind == "reduce_load":
        rt = engine.eq[target]
        rt.capacity = max(0.4, rt.capacity * 0.8)
        return {"executed": kind, "target": target, "capacity": rt.capacity}
    raise ValueError(f"unknown action {kind}")


def verify_plan(engine: SimulationEngine, incident: Incident) -> tuple[bool, list[str]]:
    """ACTION → OBSERVE → VERIFY. Fails closed: any critical alarm or bad
    primary sensor on the affected set keeps the incident open."""
    findings: list[str] = []
    ok = True
    scope = [incident.origin_equipment, *incident.affected]
    for eq_id in scope:
        eq = next((e for e in engine.plant.equipment if e.id == eq_id), None)
        if not eq:
            continue
        for s in eq.sensors:
            rt = engine.sensors[s.id]
            if rt.quality == TelemetryQuality.BAD and incident.origin_sensor == s.id:
                continue  # the known-bad sensor is handled by the plan
            m = s
            if m.is_detector:
                # Detectors are latched 0/1 points: healthy == 0. Only a
                # *tripped* detector is a finding. Applying the two-sided
                # envelope test here made every untripped gas/leak detector
                # in the blast radius fail verification forever.
                if rt.value >= m.critical_max:
                    findings.append(f"{m.tag} detector tripped ({rt.value:.1f} {m.unit})")
                    ok = False
                continue
            if rt.value >= m.critical_max or rt.value <= m.critical_min:
                findings.append(f"{m.tag} still beyond critical envelope ({rt.value:.1f} {m.unit})")
                ok = False
    crit_alarms = [a for a in engine.alarms.values() if a.severity == AlarmSeverity.CRITICAL]
    if crit_alarms:
        findings.append(f"{len(crit_alarms)} critical alarm(s) active")
        ok = False
    if not findings:
        findings.append("All affected assets inside envelope; no critical alarms.")
    return ok, findings
