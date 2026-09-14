"""Three-agent, model-driven recovery decision for the simulation.

The deterministic pipeline computed a recovery plan from engine state and the
failover route from a fixed rule, while the "agents" handed back narrative text
that never influenced the plan. This module makes the agents the *source of the
decision*.

Three agents — Diagnostic, Operations, Safety — each call the local model over
the same evidence pack the deterministic pipeline gathered (sensor state,
topology neighbourhood, maintenance metadata, retrieved procedures) and return
a small JSON object. Their answers are merged into a :class:`RecoveryDecision`
whose route is expressed in real connection IDs from the plant graph, validated
against the engine. The engine then executes exactly those IDs, and the frontend
animates exactly those IDs.

When the local model cannot be reached there is no silent fallback: the decision
reports ``available=False`` with "LOCAL MODEL UNAVAILABLE" and the incident is
left open rather than "recovered" by a script. A different sensor changes the
evidence pack, so the agents are free to return a different diagnosis and a
different route — nothing is keyed to a specific tag.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from backend.simulation.engine import SimulationEngine
from backend.simulation.models import Incident
from backend.simulation.retrieval import RetrievalUnavailable, get_retriever

logger = logging.getLogger(__name__)

#: Tests set this to a fake (role, system, user) -> (text, model). Production
#: leaves it None so the real local model is used.
_ask_override: Any = None


#: The roles this module runs. Exactly three, matching the console's panels.
ROLES = ("diagnostic", "operations", "safety")

#: Diagnostic -> domain (reasoning) model; Operations -> reasoning; Safety -> domain.
_ROLE_MODEL: dict[str, str] = {
    "diagnostic": "reasoning",
    "operations": "reasoning",
    "safety": "domain",
}


class RecoveryDecision(BaseModel):
    incident_id: str
    available: bool = False
    model: str | None = None
    error: str | None = None

    diagnosis: str = ""
    failure_mode: str | None = None
    origin_sensor: str | None = None
    affected_equipment: list[str] = Field(default_factory=list)

    #: The route the Operations agent chose, as ordered connection IDs.
    route: list[str] = Field(default_factory=list)
    block: list[str] = Field(default_factory=list)
    restore: list[str] = Field(default_factory=list)

    safety_confirmed: bool = False
    safety_concerns: list[str] = Field(default_factory=list)
    rationale: str = ""

    @property
    def reroute(self) -> dict:
        """The executable action this decision maps to."""
        return {
            "kind": "reroute",
            "target": self.origin_sensor or "",
            "block": self.block,
            "restore": self.restore,
            "route": self.route,
        }


# ---------------------------------------------------------------- evidence


def _equipment_context(engine: SimulationEngine, incident: Incident) -> dict[str, Any]:
    by_id = {e.id: e for e in engine.plant.equipment}
    origin = incident.origin_equipment

    def describe(eq_id: str) -> dict:
        e = by_id[eq_id]
        rt = engine.eq[eq_id]
        return {
            "id": e.id,
            "tag": e.tag,
            "kind": e.kind.value,
            "area": e.area_id,
            "state": rt.state.value,
            "capacity": round(rt.capacity, 3),
            "failure_modes": e.failure_modes,
            "last_inspection": e.last_inspection,
        }

    scope = [origin, *incident.affected]
    upstream = [describe(i) for i in engine.upstream.get(origin, []) if i in by_id]
    downstream = [describe(i) for i in engine.downstream.get(origin, []) if i in by_id]
    sensors = []
    for eq_id in scope:
        if eq_id not in by_id:
            continue
        for s in by_id[eq_id].sensors:
            rt = engine.sensors.get(s.id)
            m = s
            sensors.append({
                "id": s.id,
                "tag": s.tag,
                "equipment_id": s.equipment_id,
                "measurement": s.measurement.value,
                "unit": s.unit,
                "value": round(rt.value, 2) if rt else None,
                "quality": rt.quality.value if rt else "unknown",
                "normal": [m.normal_min, m.normal_max],
                "critical": [m.critical_min, m.critical_max],
                "is_detector": m.is_detector,
            })
    paths = [
        {
            "id": c.id,
            "source": c.source,
            "source_tag": by_id[c.source].tag if c.source in by_id else c.source,
            "target": c.target,
            "target_tag": by_id[c.target].tag if c.target in by_id else c.target,
            "medium": c.medium,
            "enabled": c.enabled,
            "leaking": c.leaking,
            "status": c.status.value,
        }
        for c in engine.plant.connections
        if c.source in scope or c.target in scope
    ]
    alts = []
    if incident.origin_sensor:
        for s in engine.alternate_sensors(incident.origin_sensor):
            rt = engine.sensors.get(s.id)
            alts.append({"id": s.id, "tag": s.tag, "equipment_id": s.equipment_id,
                         "measurement": s.measurement.value,
                         "quality": rt.quality.value if rt else "unknown"})
    return {
        "origin": describe(origin) if origin in by_id else {"id": origin},
        "upstream": upstream,
        "downstream": downstream,
        "affected": [describe(i) for i in incident.affected if i in by_id],
        "sensors": sensors,
        "paths": paths,
        "alternate_sensors": alts,
    }


def _documents(engine: SimulationEngine, incident: Incident) -> list[dict[str, Any]]:
    origin = incident.origin_equipment
    eq = next((e for e in engine.plant.equipment if e.id == origin), None)
    if eq is None:
        return []
    mode = next((m for m in engine.plant.failure_modes if m.id == incident.failure_mode), None)
    measurement = (
        engine.sensor_model[incident.origin_sensor].measurement.value
        if incident.origin_sensor else None
    )
    area = next((a.name for a in engine.plant.areas if a.id == eq.area_id), eq.area_id)
    try:
        _, hits = get_retriever().for_incident(
            equipment_kind=eq.kind.value,
            equipment_tag=eq.tag,
            measurement=measurement,
            mechanism=mode.mechanism if mode else incident.failure_mode,
            area=area,
            k=3,
        )
    except RetrievalUnavailable:
        return []
    return [
        {"id": h.document_id, "title": h.title, "passage": h.text[:300].strip(),
         "citation": h.citation}
        for h in hits
    ]


def build_decision_evidence(engine: SimulationEngine, incident: Incident) -> dict[str, Any]:
    return {
        "incident_id": incident.id,
        "severity": incident.severity.value,
        "failure_mode": incident.failure_mode,
        "origin_sensor": incident.origin_sensor,
        "equipment": _equipment_context(engine, incident),
        "documents": _documents(engine, incident),
        "alarms": [
            {"id": a.id, "equipment_id": a.equipment_id, "severity": a.severity.value,
             "message": a.message}
            for a in engine.alarms.values()
        ],
    }


# ---------------------------------------------------------------- model call

def _get_provider() -> Any:
    """Build a fresh provider for each call.

    ``httpx.AsyncClient`` binds its connection pool to the event loop that first
    uses it. A cached provider survives ``asyncio.run`` closing that loop and the
    next call then fails with "Event loop is closed". A fresh client per agent
    turn is the correct fix — and it is cheap at this call rate.
    """
    from backend.config import Settings  # noqa: PLC0415
    from backend.models.providers.openai_compatible import OpenAICompatibleProvider  # noqa: PLC0415
    from backend.security.egress import policy_from_settings  # noqa: PLC0415

    settings = Settings()
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or None,
        timeout_seconds=settings.llm_timeout_seconds,
        egress=policy_from_settings(settings),
    )


def _model_name(role: str) -> str:
    from backend.config import Settings  # noqa: PLC0415

    settings = Settings()
    return getattr(settings, f"{_ROLE_MODEL[role]}_model") or ""


def _ask(role: str, system: str, user: str) -> tuple[str, str]:
    """Run one agent turn. Returns (text, model) or raises ModelUnavailableError."""
    from backend.models.providers.base import ChatMessage  # noqa: PLC0415
    from backend.models.router.model_router import ModelUnavailableError  # noqa: PLC0415

    model = _model_name(role)
    if not model:
        raise ModelUnavailableError(
            f"no model configured for role '{_ROLE_MODEL[role]}' — set the model in .env"
        )
    provider = _get_provider()
    result = asyncio.run(provider.chat(
        model=model,
        messages=[ChatMessage(role="system", content=system),
                  ChatMessage(role="user", content=user)],
        temperature=0.1,
        max_tokens=512,
    ))
    return result.content, model


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply, tolerating prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


# ---------------------------------------------------------------- decisions


def _json_field(data: dict[str, Any], key: str, default: Any = None) -> Any:
    return data.get(key, default)


#: Signature of the model-call seam. Tests inject a fake here so the suite runs
#: hermetically; production uses :func:`_ask` (the real local model).
_ASK_SIGNATURE = tuple[str, str, str]  # (role, system, user) -> (text, model)


def run_incident_decision(
    engine: SimulationEngine,
    incident: Incident,
    *,
    ask: Any | None = None,
) -> RecoveryDecision:
    """Run the three agents and validate their merged decision against the engine.

    ``ask`` is the model-call seam: ``(role, system, user) -> (text, model)``.
    Tests pass a fake; production uses the real local model. Any model failure
    short-circuits to ``available=False`` with a clear "LOCAL MODEL UNAVAILABLE"
    message — never a fabricated recovery.
    """
    ask = ask or _ask_override or _ask
    evidence = build_decision_evidence(engine, incident)
    by_id = {c.id: c for c in engine.plant.connections}
    equipment_ids = {e.id for e in engine.plant.equipment}

    decision = RecoveryDecision(
        incident_id=incident.id,
        origin_sensor=incident.origin_sensor,
        failure_mode=incident.failure_mode,
    )

    try:
        models: list[str] = []

        # --- Diagnostic ----------------------------------------------------
        diag = _extract_json(ask(
            "diagnostic",
            "You are a plant diagnostic agent. Answer ONLY with a JSON object and no prose.",
            (
                "A sensor was disabled. The origin asset is "
                f"{evidence['equipment']['origin'].get('tag', 'unknown')} "
                f"(id {evidence['equipment']['origin'].get('id')}). "
                "State which asset is affected and why.\n\n"
                f"Affected assets (copy ids only from here): "
                f"{[a['id'] for a in evidence['equipment']['affected']]}\n\n"
                "Return JSON only:\n"
                '{"affected_equipment": ["<id>", ...], "diagnosis": "one sentence", '
                '"failure_mode": "declared mode or null"}'
            ),
        )[0])
        models.append("diagnostic")
        affected = [
            a for a in _json_field(diag, "affected_equipment", [])
            if a in equipment_ids
        ]
        decision.affected_equipment = affected or list(incident.affected)
        decision.diagnosis = str(_json_field(diag, "diagnosis", "")).strip()
        fm = _json_field(diag, "failure_mode")
        if fm in [m.id for m in engine.plant.failure_modes]:
            decision.failure_mode = fm

        # --- Operations ----------------------------------------------------
        candidate_lines = [p["id"] for p in evidence["equipment"]["paths"]]
        ops = _extract_json(ask(
            "operations",
            "You are a plant operations agent. Answer ONLY with a JSON object and no prose.",
            (
                "A fault disabled the origin asset. Choose a recovery route over the "
                "plant's real connection graph: restore the lines that keep the process "
                "flowing and block the faulted line if one is shown as disabled.\n\n"
                f"Candidate connection ids (copy ONLY from this list): {candidate_lines}\n\n"
                "Return JSON only, copying ids exactly:\n"
                '{"route": ["<id>", ...], "block": ["<id>", ...], '
                '"restore": ["<id>", ...], "rationale": "one sentence"}'
            ),
        )[0])
        models.append("operations")
        route = [r for r in _json_field(ops, "route", []) if r in by_id]
        block = [r for r in _json_field(ops, "block", []) if r in by_id]
        restore = [r for r in _json_field(ops, "restore", []) if r in by_id]
        decision.route = route
        decision.block = block
        decision.restore = restore
        decision.rationale = str(_json_field(ops, "rationale", "")).strip()

        # --- Safety --------------------------------------------------------
        sf = _extract_json(ask(
            "safety",
            "You are a plant safety and verification agent. Answer ONLY with JSON and no prose.",
            (
                "Confirm whether the proposed recovery route is safe for this plant.\n\n"
                f"Evidence (JSON): {json.dumps(evidence, default=str)}\n"
                f"Proposed route: block={block}, restore={restore}\n\n"
                "Return JSON only:\n"
                '{"safe": true_or_false, "concerns": ["concern", ...]}'
            ),
        )[0])
        models.append("safety")
        decision.safety_confirmed = bool(_json_field(sf, "safe", False))
        decision.safety_concerns = [str(c) for c in _json_field(sf, "concerns", [])]

        decision.available = True
        decision.model = ",".join(dict.fromkeys(models))
    except Exception as exc:  # model/router/json failures all mean the same thing
        decision.available = False
        decision.error = f"LOCAL MODEL UNAVAILABLE — {exc.__class__.__name__}: {exc}"
        logger.warning("incident decision unavailable for %s: %s", incident.id, decision.error)

    return decision
