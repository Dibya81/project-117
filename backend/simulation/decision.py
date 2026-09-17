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
import inspect
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

#: Fixed system prompts per role. Kept as constants so the self-correction turn
#: re-asks the SAME agent with the SAME role, only with the rejection appended.
OPS_SYSTEM = "You are a plant operations agent. Answer ONLY with a JSON object and no prose."
SAFETY_SYSTEM = "You are a plant safety and verification agent. Answer ONLY with JSON and no prose."

#: Fallback role bucket — only consulted when no per-agent model is set.
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

    #: What each agent's OWN turn actually produced, so the console renders the
    #: backend state instead of inferring success: ``completed`` (its turn
    #: returned usable output), ``rejected`` (Safety declined the route),
    #: ``failed`` (the turn errored or returned unusable output) or ``skipped``
    #: (it was never reached because an earlier agent failed). A panel may only
    #: claim success for a role marked ``completed``.
    agent_status: dict[str, str] = Field(default_factory=dict)

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
        # An alarm carries the sensor it fired on, not an equipment id; the
        # equipment is the sensor's owner. Reading `a.equipment_id` raised
        # AttributeError whenever any alarm was live, which 500'd the whole
        # decision — so a SECOND incident raised while an alarm stood could
        # never decide and stayed in awaiting_approval forever.
        "alarms": [
            {
                "id": a.id,
                "sensor_id": a.sensor_id,
                "equipment_id": (
                    engine.sensor_model[a.sensor_id].equipment_id
                    if a.sensor_id in engine.sensor_model
                    else None
                ),
                "tag": a.tag,
                "severity": a.severity.value,
                "message": a.message,
            }
            for a in engine.alarms.values()
        ],
    }


def safety_facts(evidence: dict[str, Any]) -> dict[str, Any]:
    """The facts the safety verdict actually depends on — and nothing else.

    Handing a small local model the whole evidence pack produced noisy verdicts:
    a one-letter concern, or a refusal caused by the incident's OWN out-of-service
    point being counted as a hazard. The route question is narrow, so the question
    put to the Safety agent is narrowed to match: is any critical alarm active, is
    any READABLE point outside its critical band, and are there points that are
    already out of service (the incident itself, not a hazard).
    """
    sensors = evidence.get("equipment", {}).get("sensors", [])

    def beyond_critical(s: dict[str, Any]) -> bool:
        crit = s.get("critical") or [None, None]
        lo, hi = crit[0], crit[1]
        value = s.get("value")
        if value is None:
            return False
        return (lo is not None and value <= lo) or (hi is not None and value >= hi)

    readable = [s for s in sensors if s.get("quality") not in ("bad", "stale")]
    # Detectors are latched 0/1 points: a healthy detector reads 0 and a
    # tripped detector reads > 0. Treating 0 as "beyond critical_min"
    # made every plant with a healthy gas/leak detector fail Safety and
    # therefore fail every recovery — the incident could never resolve.
    # verify_plan() uses the same 0/1 rule; the facts here must match it.
    readable = [s for s in readable if not s.get("is_detector")]
    return {
        "critical_alarms": [
            {"id": a.get("id"), "tag": a.get("tag"), "message": a.get("message")}
            for a in evidence.get("alarms", [])
            if a.get("severity") == "critical"
        ],
        "readable_sensors_beyond_critical": [
            {"id": s.get("id"), "tag": s.get("tag"), "value": s.get("value"),
             "critical": s.get("critical")}
            for s in readable
            if beyond_critical(s)
        ],
        "out_of_service_points": [
            s.get("id") for s in sensors if s.get("quality") in ("bad", "stale")
        ],
    }


# ---------------------------------------------------------------- model call

def _get_provider() -> Any:
    """Build a provider each call.

    ``httpx.AsyncClient`` binds its connection pool to the event loop that first
    uses it. A cached provider survives ``asyncio.run`` closing that loop and the
    next call then fails with "Event loop is closed". A fresh client per agent
    turn is the correct fix — and it is cheap at this call rate.

    When called from within an already-running event loop (the normal async
    path) this simply creates a new provider; the caller awaits the chat method.
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
    """Resolve the model for a given agent role.

    Resolution order (first non-empty wins):
      1. Per-agent override  (diagnostic_model / operations_model / safety_model)
      2. Shared decision_model override (applies to all three)
      3. Role-bucket model  (reasoning_model / domain_model)

    The per-agent overrides are what lets each of the three agents run a
    *different* local Ollama model concurrently: qwen3:1.7b for diagnostics,
    llama3.2:3b for operations, gemma3:1b for safety.
    """
    from backend.config import Settings  # noqa: PLC0415

    settings = Settings()
    # 1. Per-agent model (highest priority)
    per_agent_field = f"{role}_model"  # diagnostic_model / operations_model / safety_model
    per_agent = str(getattr(settings, per_agent_field, "") or "").strip()
    if per_agent:
        return per_agent
    # 2. Shared decision model override
    override = str(getattr(settings, "decision_model", "") or "").strip()
    if override:
        return override
    # 3. Role bucket fallback
    return getattr(settings, f"{_ROLE_MODEL[role]}_model") or ""


#: Models that emit hidden chain-of-thought before their answer. On Ollama the
#: reasoning tokens are counted against ``max_tokens`` but are NOT part of
#: ``message.content``, so a budget that fits the answer can still truncate the
#: reply to nothing. Measured on this machine: ``qwen3:1.7b`` spends ~1720
#: characters (~400 tokens) thinking, so the production budget of 400 returned
#: ``finish_reason=length`` with ``content=''`` on *every* call — the Diagnostic
#: agent could never answer, and the incident never recovered.
_REASONING_MODELS = ("qwen3", "deepseek-r1", "qwythos", "magistral")


def max_tokens_reached(used_tokens: int, budget: int) -> bool:
    """Whether a blank reply was caused by the token budget running out.

    A truncated reply reports ``completion_tokens`` equal to the budget (and the
    OpenAI-compatible shim reports ``finish_reason="length"``). Either signal is
    conclusive, because an identical retry would truncate identically.
    """
    return used_tokens >= budget


def _max_tokens() -> int:
    """Reply budget for one agent turn, from settings (default 1024)."""
    from backend.config import Settings  # noqa: PLC0415

    try:
        configured = int(Settings().decision_max_tokens)
    except (TypeError, ValueError):
        configured = 0
    budget = configured if configured > 0 else _AGENT_MAX_TOKENS
    return max(budget, _REASONING_MIN_TOKENS)


#: Output budget for one agent turn, when ``P117_DECISION_MAX_TOKENS`` is not
#: set. The floor must clear a reasoning model's chain-of-thought: qwen3:1.7b
#: spends ~1700 characters in hidden reasoning before it emits anything, so a
#: budget sized only for the JSON object truncated the reply to an EMPTY
#: completion (``finish_reason: "length"``). See ``_max_tokens``.
_AGENT_MAX_TOKENS = 1400

#: Hard floor for a reasoning model's output budget.
#:
#: A reasoning model is charged for its hidden trace before it emits a single
#: character of content, so a budget that comfortably fits the JSON can still
#: truncate the reply to nothing. This floor is applied on top of whatever is
#: configured — the budget is a ceiling, not a cost, so the headroom is free and
#: silently starving the agent is not worth saving a few tokens of latency.
_REASONING_MIN_TOKENS = 2048


def _local_extra_body() -> dict[str, Any]:
    """Ollama request options, keyed where Ollama actually reads them.

    Two settings decide whether a small reasoning model can answer at all:

    ``num_ctx``
        Ollama's default context window is small. When prompt plus reasoning
        overflows it the reply is truncated before any content is emitted —
        ``content: ""`` with ``finish_reason: "length"``.
    ``think``
        qwen3 is a thinking model: its chain-of-thought is charged against
        ``max_tokens``, so at a small budget it thinks and emits nothing. For a
        strict-JSON contract the reasoning is not wanted, only the answer.

    They are sent both top-level and under ``options``. Ollama ignores unknown
    top-level keys on its OpenAI-compatible ``/v1`` route but honours its
    documented parameter block, so this targets the path that is actually read.
    """
    from backend.config import Settings  # noqa: PLC0415

    settings = Settings()
    num_ctx = int(getattr(settings, "llm_num_ctx", 4096) or 4096)
    opts: dict[str, Any] = {"num_ctx": num_ctx}
    # Suppress the hidden reasoning trace unless it is explicitly wanted.
    #
    # This read `getattr(settings, "llm_think", "")` against a setting that did
    # not exist, so the value was always "" and `think` was NEVER sent. qwen3:1.7b
    # then reasoned until the output budget ran out and returned an empty
    # completion, which is why every incident failed in the Diagnostic turn. The
    # setting now exists and defaults to "off"; only an explicit "on" re-enables
    # the trace.
    think = str(getattr(settings, "llm_think", "off") or "").strip().lower()
    if think not in {"on", "true", "1", "yes", "enabled"}:
        opts["think"] = False
    return {**opts, "options": opts}


async def _ask_async(role: str, system: str, user: str) -> tuple[str, str]:
    """Async agent turn — awaits the model response without blocking.

    Uses Ollama's ``keep_alive`` option (via extra_body) to keep the model
    loaded between turns so re-invocations on the same request pay no
    load penalty. Each of the three agents targets a different model, so
    they can genuinely run concurrently via ``asyncio.gather``.

    Reasoning models (``qwen3:1.7b``) are asked to skip their hidden trace
    (``think=false``) and are given a budget that leaves room for it if the
    server ignores the flag. A reply that is empty *because the token budget ran
    out* is not retried: the retry would be byte-identical and is guaranteed to
    truncate the same way, so retrying only stalled the incident. Only a
    genuinely blank reply from a server under load is retried.
    """
    from backend.models.providers.base import ChatMessage  # noqa: PLC0415
    from backend.models.router.model_router import ModelUnavailableError  # noqa: PLC0415

    model = _model_name(role)
    if not model:
        raise ModelUnavailableError(
            f"no model configured for role '{role}' — set P117_{role.upper()}_MODEL in .env"
        )
    provider = _get_provider()
    # Structured JSON output: small token budget, no chain-of-thought.
    # keep_alive=-1 tells Ollama to keep the model hot indefinitely so the next
    # call (self-correction turn or the next incident) loads instantly.
    extra_body: dict[str, Any] = {"keep_alive": -1, **_local_extra_body()}
    if model.lower().startswith(_REASONING_MODELS):
        extra_body["think"] = False
    budget = _max_tokens()
    last_finish: str = "?"
    for attempt in range(3):
        result = await provider.chat(
            model=model,
            messages=[
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user),
            ],
            temperature=0.0,
            max_tokens=budget,
            extra_body=extra_body,
        )
        content = result.content
        if content and content.strip():
            return content, model
        # A blank reply has two very different causes and only one of them is
        # worth retrying: a server under load that answered nothing (retry), and
        # a reasoning model whose hidden trace consumed the whole budget so the
        # reply was cut off before any content was emitted (do NOT retry — the
        # identical call truncates identically and only adds dead air).
        used = int((result.usage or {}).get("completion_tokens") or 0)
        last_finish = result.finish_reason or "?"
        if last_finish == "length" or max_tokens_reached(used, budget):
            raise ModelUnavailableError(
                f"{role} model {model} produced no answer: the reply hit the "
                f"{budget}-token budget before emitting content "
                f"(finish_reason={last_finish}, completion_tokens={used}). Raise "
                "P117_DECISION_MAX_TOKENS or use a non-reasoning model for this role."
            )
        logger.warning(
            "decision: %s returned empty response (finish=%s), retry %d",
            role, last_finish, attempt,
        )
    raise ModelUnavailableError(
        f"{role} model {model} returned empty response 3 times (finish={last_finish})"
    )


def _ask(role: str, system: str, user: str) -> tuple[str, str]:
    """Synchronous wrapper — only used by legacy call sites and tests.

    Production code paths use ``_ask_async`` inside ``run_incident_decision_async``.
    """
    return asyncio.run(_ask_async(role, system, user))


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

def _validate_recovery_decision(
    engine: SimulationEngine,
    incident: Incident,
    decision: RecoveryDecision,
) -> list[str]:
    by_id = {c.id: c for c in engine.plant.connections}
    errors: list[str] = []
    block = list(dict.fromkeys(decision.block))
    restore = list(dict.fromkeys(decision.restore))
    route = list(dict.fromkeys(decision.route))
    decision.block = block
    decision.restore = restore
    decision.route = route

    overlap = sorted(set(block) & set(restore))
    if overlap:
        errors.append(f"block and restore overlap: {', '.join(overlap)}")

    # A decision that changes nothing is not a recovery. Without this rule the
    # agents could return empty block/restore/route, Safety would approve the
    # empty proposal, the decision would be published as `available` — and the
    # console showed "Safety verified" with "No route chosen yet" while the
    # engine's reroute then failed with nothing to actuate. The plant must be
    # told to change at least one real line.
    if not block and not restore:
        errors.append(
            "recovery must change the topology: name at least one line to block "
            "or to restore"
        )

    for cid in [*route, *block, *restore]:
        if cid not in by_id:
            errors.append(f"unknown connection id: {cid}")

    if restore and not route:
        errors.append("restore requires an explicit route")

    blocked = set(block)
    for cid in route:
        if cid in blocked:
            errors.append(f"route depends on blocked connection: {cid}")

    if route and all(cid in by_id for cid in route):
        prev = by_id[route[0]]
        for cid in route[1:]:
            cur = by_id[cid]
            if prev.target != cur.source:
                errors.append(
                    f"route is not ordered topology: {prev.id} ends at {prev.target}, "
                    f"{cur.id} starts at {cur.source}"
                )
                break
            prev = cur

        route_start = by_id[route[0]].source
        route_end = by_id[route[-1]].target
        scope = {incident.origin_equipment, *incident.affected}
        if route_start not in scope and route_end not in scope:
            errors.append(
                "route must start or end inside the incident circuit "
                f"({incident.origin_equipment})"
            )

    for cid in restore:
        if cid in by_id:
            c = by_id[cid]
            scope = {incident.origin_equipment, *incident.affected}
            if c.source not in scope and c.target not in scope and cid not in route:
                errors.append(f"restored connection is not an alternative incident path: {cid}")

    if decision.safety_confirmed is not True:
        errors.append("safety did not confirm the final route")

    return errors


#: Signature of the model-call seam. Tests inject a fake here so the suite runs
#: hermetically; production uses :func:`_ask` (the real local model).
_ASK_SIGNATURE = tuple[str, str, str]  # (role, system, user) -> (text, model)


async def run_incident_decision_async(
    engine: SimulationEngine,
    incident: Incident,
    *,
    ask: Any | None = None,
    prior_attempt: dict[str, Any] | None = None,
) -> RecoveryDecision:
    """Async three-agent recovery decision — Diagnostic and Operations run concurrently.

    ``ask`` is the async model-call seam: ``(role, system, user) -> (text, model)``.
    Tests pass an async fake; production uses :func:`_ask_async`.

    Concurrency model:

      asyncio.gather(diagnostic_turn, operations_turn)  ← parallel
             ↓
      safety_turn  ← sequential (needs Operations' proposed route)

    ``prior_attempt`` is a route the engine already executed for this incident
    whose verification failed, as ``{"route", "block", "restore", "findings"}``.
    """
    raw_ask = ask or _ask_override or _ask_async
    if raw_ask is not None and not inspect.iscoroutinefunction(raw_ask):
        sync_fn = raw_ask

        async def _async_wrap(role: str, system: str, user: str) -> tuple[str, str]:
            return sync_fn(role, system, user)

        ask_fn = _async_wrap
    else:
        ask_fn = raw_ask

    evidence = build_decision_evidence(engine, incident)
    by_id = {c.id: c for c in engine.plant.connections}
    equipment_ids = {e.id for e in engine.plant.equipment}

    decision = RecoveryDecision(
        incident_id=incident.id,
        origin_sensor=incident.origin_sensor,
        failure_mode=incident.failure_mode,
    )

    # Evidence sent to each agent is narrowed to what it actually needs.
    # Sending the full evidence pack to every model was the source of "noisy
    # verdicts" and "a refusal caused by the incident's OWN out-of-service
    # point being counted as a hazard".
    origin_tag = evidence["equipment"]["origin"].get("tag", "unknown")
    origin_id = evidence["equipment"]["origin"].get("id", "")
    affected_ids = [a["id"] for a in evidence["equipment"]["affected"]]

    # Sensor evidence: just the directly related readings, not the whole graph.
    sensor_summary = [
        f"{s['tag']}={s['value']} {s.get('quality','?')}"
        for s in evidence["equipment"]["sensors"][:6]
    ]
    # Render each candidate WITH its endpoints.
    #
    # The prompt tells the model that "route is an ordered path: each line must
    # end where the next begins" — but the evidence used to be a flat list of
    # bare connection ids, so the model had no way to know where any line began
    # or ended. It was being asked to satisfy a rule it could not see the inputs
    # for: for some assets it guessed a connected pair, and for others it
    # proposed two lines that do not join, which the validator then rejected
    # ("route is not ordered topology: pl-042 ends at e-VS-1172, pl-043 starts at
    # e-E-1004"). Giving the endpoints makes the rule answerable.
    def _line(conn: dict) -> str:
        a_tag = conn.get("source_tag") or conn.get("source")
        b_tag = conn.get("target_tag") or conn.get("target")
        state = "" if conn.get("enabled", True) else "  [SHUT]"
        return f"{conn['id']}: {a_tag} -> {b_tag}{state}"

    candidate_lines = [_line(p) for p in evidence["equipment"]["paths"]]
    disabled_lines = [_line(p) for p in evidence["equipment"]["paths"] if not p.get("enabled")]

    retry_note = ""
    if prior_attempt:
        tried = {k: list(prior_attempt.get(k) or []) for k in ("route", "block", "restore")}
        retry_note = (
            "\n\nA previous recovery you chose for this same incident was already "
            "executed, and the plant's verification FAILED. Do not return that route again.\n"
            f"Previous route already tried: {json.dumps(tried)}\n"
            f"Why it was rejected: {json.dumps(list(prior_attempt.get('findings') or []))}\n"
        )

    try:
        models: list[str] = []

        # ---- Diagnostic prompt (qwen3:1.7b) --------------------------------
        # Narrow context: just the origin asset, affected list, and sensor snapshot.
        diag_system = "You are a plant diagnostic agent. Answer ONLY with a JSON object and no prose."
        diag_user = (
            f"A sensor was disabled on asset {origin_tag} (id {origin_id}). "
            "State which assets are affected and why.\n"
            f"Affected asset ids (copy only from here): {affected_ids}\n"
            f"Recent sensor readings: {sensor_summary}\n"
            "Return JSON only — no prose, no code fences:\n"
            '{"affected_equipment": ["<id>", ...], "diagnosis": "one sentence", '
            '"failure_mode": "declared mode or null", "confidence": 0.0}'
        )

        # ---- Operations prompt (llama3.2:3b) --------------------------------
        # Narrow context: just the candidate connection ids and the rule set.
        ops_system = OPS_SYSTEM
        ops_user = (
            "A fault disabled the origin asset. Recover it by ISOLATING the faulted "
            "section, then carrying the process around it: put the line that must be "
            "taken OUT of service in `block`, and the lines that carry the process "
            "around the fault in `restore` (and, in flow order, in `route`).\n"
            "Candidate connections — copy ids ONLY from this list. Each is drawn "
            "as `id: FROM -> TO`, which is the only way to know what joins what:\n"
            f"{chr(10).join(candidate_lines)}\n"
            f"Currently shut connections: {disabled_lines}\n"
            "Rules — the decision is rejected if any is broken:\n"
            "1. Copy ids exactly; never invent one.\n"
            "2. `route`, `block` and `restore` must be consistent: an id in `route` "
            "must NEVER appear in `block`, and an id in `block` must NEVER appear in `restore`.\n"
            "3. `route` is an ordered path: each line must end where the next begins.\n"
            "4. `restore` requires a non-empty `route`.\n"
            "5. A line that is already shut may only appear in `restore`.\n"
            "6. `block` must name at least one line and `route` must not use it.\n"
            + retry_note +
            "Return JSON only, copying ids exactly:\n"
            '{"route": ["<id>", ...], "block": ["<id>", ...], '
            '"restore": ["<id>", ...], "rationale": "one sentence"}'
        )

        # ---- CONCURRENT: Diagnostic + Operations run in parallel ------------
        # They share no inputs, so they can genuinely execute simultaneously.
        # Safety is sequential because it needs the Operations route to verify.
        logger.debug("decision: running diagnostic+operations concurrently for %s", incident.id)
        diag_raw, ops_raw = await asyncio.gather(
            ask_fn("diagnostic", diag_system, diag_user),
            ask_fn("operations", ops_system, ops_user),
            return_exceptions=True,
        )

        # ---- Diagnostic result ------------------------------------------
        # A Diagnostic that could not answer is a FAILED workflow, not a
        # footnote. The old code logged the failure, wrote "Diagnostic
        # unavailable: ModelUnavailableError" into the decision and carried on,
        # so the console showed a faulted Diagnostic next to a successful
        # Operations and a "verified" Safety — and the incident then sat open
        # forever with no way forward. If the first agent of the chain cannot
        # produce a result, nothing downstream is trustworthy: stop here, leave
        # the plant untouched, and say which agent failed.
        if isinstance(diag_raw, BaseException):
            logger.warning("diagnostic agent failed for %s: %s", incident.id, diag_raw)
            decision.available = False
            decision.agent_status = {
                "diagnostic": "failed",
                "operations": "skipped",
                "safety": "skipped",
            }
            decision.error = f"LOCAL MODEL UNAVAILABLE — diagnostic agent: {diag_raw}"
            decision.diagnosis = "Diagnostic agent did not answer — no recovery attempted."
            return decision
        else:
            diag_text = diag_raw[0] if isinstance(diag_raw, tuple) else str(diag_raw)
            diag_model = diag_raw[1] if isinstance(diag_raw, tuple) else _model_name("diagnostic")
            try:
                diag = _extract_json(diag_text)
                models.append(diag_model)
                affected = [
                    a for a in _json_field(diag, "affected_equipment", [])
                    if a in equipment_ids
                ]
                decision.affected_equipment = affected or list(incident.affected)
                decision.diagnosis = str(_json_field(diag, "diagnosis", "")).strip()
                fm = _json_field(diag, "failure_mode")
                if fm in [m.id for m in engine.plant.failure_modes]:
                    decision.failure_mode = fm
                # The turn returned a usable JSON object: only now may the
                # console's Diagnostic panel claim "Fault Diagnosed".
                decision.agent_status["diagnostic"] = "completed"
            except Exception as exc:
                # Unparseable output is a failed agent, not a diagnosis. Carrying
                # on would put a faulted Diagnostic next to a successful
                # Operations — the exact contradictory state the console showed
                # while the incident never recovered.
                logger.warning("diagnostic JSON parse failed for %s: %s", incident.id, exc)
                decision.available = False
                decision.agent_status = {
                    "diagnostic": "failed",
                    "operations": "skipped",
                    "safety": "skipped",
                }
                decision.error = (
                    "LOCAL MODEL UNAVAILABLE — diagnostic agent returned unusable "
                    f"output ({exc.__class__.__name__})"
                )
                decision.diagnosis = "Diagnostic agent returned unusable output — no recovery attempted."
                return decision

        # ---- Operations result + self-correction loop -------------------
        feedback = ""
        validation_errors: list[str] = []
        validated = False

        # Use the already-fetched ops_raw for the first attempt; then
        # self-correct up to 2 more times if the route is invalid.
        ops_attempts = [ops_raw] + [None, None]  # first result + 2 retry slots
        for attempt_i, raw in enumerate(ops_attempts):
            # For retries (attempt_i > 0), re-ask the model with feedback.
            if attempt_i > 0:
                retry_prompt = ops_user + feedback
                try:
                    raw = await ask_fn("operations", ops_system, retry_prompt)
                except Exception as exc:
                    feedback = (
                        f"\n\nA previous step did not return valid JSON ({exc.__class__.__name__}). "
                        "Return ONLY the JSON object, with no prose and no code fences."
                    )
                    continue

            if isinstance(raw, BaseException):
                feedback = (
                    f"\n\nA previous step failed ({type(raw).__name__}). "
                    "Return ONLY the JSON object, with no prose and no code fences."
                )
                continue

            ops_text = raw[0] if isinstance(raw, tuple) else str(raw)
            ops_model = raw[1] if isinstance(raw, tuple) else _model_name("operations")
            try:
                ops = _extract_json(ops_text)
            except Exception as exc:
                feedback = (
                    f"\n\nA previous step did not return valid JSON ({exc.__class__.__name__}). "
                    "Return ONLY the JSON object, with no prose and no code fences."
                )
                continue

            if ops_model not in models:
                models.append(ops_model)
            decision.route = [r for r in _json_field(ops, "route", []) if r in by_id]
            decision.block = [r for r in _json_field(ops, "block", []) if r in by_id]
            decision.restore = [r for r in _json_field(ops, "restore", []) if r in by_id]
            decision.rationale = str(_json_field(ops, "rationale", "")).strip()
            # Operations produced a parseable route proposal. Whether it is
            # ACCEPTED is decided below by the plant's own validator — the panel
            # is only allowed to say "Route Selected" once it passed.
            decision.agent_status["operations"] = "completed"

            # ---- Safety (gemma3:1b) — always after Operations ---------------
            # Narrow context: only the facts the safety verdict depends on.
            safety_user = (
                "Decide whether the proposed recovery route is safe to execute now.\n"
                "Answer safe=true when ALL hold: `critical_alarms` is empty, "
                "`readable_sensors_beyond_critical` is empty, and the route is not empty. "
                "The points in `out_of_service_points` are the incident itself — they are "
                "known and are NOT a hazard. Answer safe=false only for one of the two "
                "non-empty lists, and name it.\n\n"
                f"Safety facts: {json.dumps(safety_facts(evidence), default=str)}\n"
                f"Proposed: block={decision.block}, restore={decision.restore}, "
                f"route={decision.route}\n"
                "Return JSON only:\n"
                '{"safe": true_or_false, "concerns": ["a specific concern", ...]}'
            )
            try:
                sf_raw = await ask_fn("safety", SAFETY_SYSTEM, safety_user)
                sf_text = sf_raw[0] if isinstance(sf_raw, tuple) else str(sf_raw)
                sf_model = sf_raw[1] if isinstance(sf_raw, tuple) else _model_name("safety")
                sf = _extract_json(sf_text)
            except Exception as exc:
                logger.warning("safety agent failed for %s: %s", incident.id, exc)
                decision.agent_status["safety"] = "failed"
                feedback = (
                    f"\n\nA previous step did not return valid JSON ({exc.__class__.__name__}). "
                    "Return ONLY the JSON object, with no prose and no code fences."
                )
                continue

            if sf_model not in models:
                models.append(sf_model)
            decision.safety_confirmed = bool(_json_field(sf, "safe", False))
            decision.safety_concerns = [str(c) for c in _json_field(sf, "concerns", [])]
            # The Safety agent's REAL verdict: "completed" only when it approved
            # the proposed route, "rejected" when it declined it. It never reads
            # VERIFIED from the fact that it merely replied.
            decision.agent_status["safety"] = "completed" if decision.safety_confirmed else "rejected"

            validation_errors = _validate_recovery_decision(engine, incident, decision)
            validated = True
            if not validation_errors:
                break
            feedback = (
                "\n\nYour previous answer was "
                + json.dumps({
                    "route": decision.route,
                    "block": decision.block,
                    "restore": decision.restore,
                })
                + " and the plant's validator rejected it: "
                + "; ".join(validation_errors)
                + ". Return corrected JSON only, fixing exactly those problems."
            )

        if not validated:
            decision.available = False
            decision.agent_status["operations"] = "failed"
            decision.agent_status.setdefault("safety", "skipped")
            decision.error = (
                "LOCAL MODEL UNAVAILABLE — the agents did not return a usable "
                "decision (no valid JSON in three attempts)"
            )
            decision.safety_confirmed = False
            return decision

        if validation_errors:
            # The agents' answer was REJECTED by the plant's own validator. Say
            # which of the two happened: a Safety refusal is a different outcome
            # from a malformed route, and the console shows the difference rather
            # than one generic "unavailable".
            safety_refused = any("safety did not confirm" in e for e in validation_errors)
            decision.available = False
            decision.agent_status["operations"] = "failed"
            decision.agent_status.setdefault(
                "safety", "rejected" if safety_refused else "failed"
            )
            decision.error = (
                ("SAFETY CHECK FAILED — " if safety_refused else "RECOVERY DECISION INVALID — ")
                + "; ".join(validation_errors)
            )
            decision.safety_confirmed = False
            decision.safety_concerns = [*decision.safety_concerns, *validation_errors]
            return decision

        decision.available = True
        decision.agent_status["diagnostic"] = "completed"
        decision.agent_status["operations"] = "completed"
        decision.agent_status["safety"] = "completed"
        decision.model = ",".join(dict.fromkeys(models))
    except Exception as exc:  # model/router/json failures all mean the same thing
        decision.available = False
        for role in ROLES:
            decision.agent_status.setdefault(role, "failed")
        decision.error = f"LOCAL MODEL UNAVAILABLE — {exc.__class__.__name__}: {exc}"
        logger.warning("incident decision unavailable for %s: %s", incident.id, decision.error)

    return decision


def run_incident_decision(
    engine: SimulationEngine,
    incident: Incident,
    *,
    ask: Any | None = None,
    prior_attempt: dict[str, Any] | None = None,
) -> RecoveryDecision:
    """Synchronous wrapper for backward-compatible call sites.

    The real work is done by :func:`run_incident_decision_async`. This wrapper
    runs it in a new event loop. Production code that already has a running
    event loop (the FastAPI async handler) should call the async version
    directly via ``await``.
    """
    # When _ask_override is set (tests), translate the sync override into the
    # async interface the new implementation expects.
    async_ask = ask or _ask_override
    if async_ask is not None and not inspect.iscoroutinefunction(async_ask):
        # Wrap the legacy sync (role, system, user) -> (text, model) seam so
        # tests that inject a synchronous fake continue to work unchanged.
        sync_fn = async_ask

        async def _async_wrap(role: str, system: str, user: str) -> tuple[str, str]:
            return sync_fn(role, system, user)

        async_ask = _async_wrap

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(run_incident_decision_async(
                engine, incident, ask=async_ask, prior_attempt=prior_attempt,
            )))
            return future.result()
    else:
        return asyncio.run(run_incident_decision_async(
            engine, incident, ask=async_ask, prior_attempt=prior_attempt,
        ))

