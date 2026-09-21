"""Next-failure ranking for the response console.

The console's diagnostic lane needs a *prediction* payload. The signal already
exists: ``apps/web/src/lib/sim/assessment.ts`` ranks neighbour assets from live
telemetry headroom, service age, instrumentation family and topology. That
logic runs today in the browser only, which cannot feed an SSE event, so this
module is a deliberate server-side port of the same formula.

WHY a port rather than a new heuristic: the brief requires the console to reuse
the existing prediction signal instead of inventing a second one. The weights,
inputs and caveat below are the backend equivalent of `predictNextFailure`;
they read the engine's real snapshot state and the plant topology, never a
script. Keep the two in step if either changes.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from backend.simulation.engine import SimulationEngine
from backend.simulation.models import Incident, TelemetryQuality


def years_since(iso: str) -> float | None:
    """Whole years between an ISO date and today, or None when unparseable."""
    try:
        installed = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    days = (datetime.now(timezone.utc).date() - installed).days
    return max(0.0, days / 365.25)


def _neighbour_ids(engine: SimulationEngine, start: str, depth: int = 2) -> list[str]:
    """Equipment adjacency walk, identical to `neighbourIds` in assessment.ts."""
    seen = {start}
    frontier = [start]
    out: list[str] = []
    for _ in range(depth):
        nxt: list[str] = []
        for cur in frontier:
            for nb in engine.downstream.get(cur, []) + engine.upstream.get(cur, []):
                if nb in seen:
                    continue
                seen.add(nb)
                out.append(nb)
                nxt.append(nb)
        frontier = nxt
    return out


def predict_next_failure(engine: SimulationEngine, incident: Incident, limit: int = 3) -> dict:
    """Rank the at-risk neighbours of the incident origin.

    Every score is derived from recorded state: live telemetry headroom,
    installed/last-inspection dates, shared instrumentation family and graph
    distance. An assessment, never a proof — the caveat says so.
    """
    by_id = {e.id: e for e in engine.plant.equipment}
    origin = by_id.get(incident.origin_equipment)
    if origin is None:
        return {
            "available": False,
            "reason": "Origin equipment is no longer in the plant.",
            "candidates": [],
        }

    origin_sensor = (
        engine.sensor_model.get(incident.origin_sensor) if incident.origin_sensor else None
    )
    direct = set(engine.upstream.get(origin.id, [])) | set(engine.downstream.get(origin.id, []))
    candidates: list[dict] = []

    for eq_id in _neighbour_ids(engine, origin.id, 2):
        eq = by_id.get(eq_id)
        if eq is None:
            continue

        risk = 0.08
        reasons: list[str] = []

        # 1. telemetry headroom — the strongest real signal available
        worst = 0.0
        worst_tag = ""
        for s in eq.sensors:
            rt = engine.sensors.get(s.id)
            if rt is None or rt.quality != TelemetryQuality.GOOD or s.is_detector:
                continue
            span = abs(s.critical_max - s.normal_max) or abs(s.normal_max - s.normal_min) or 1.0
            into_critical = (rt.value - s.normal_max) / span
            into_warning = (rt.value - s.warning_max) / span
            score = max(into_critical, into_warning * 0.6, 0.0)
            if score > worst:
                worst = score
                worst_tag = f"{s.tag} at {rt.value:.1f} {s.unit}"
        if worst > 0:
            risk += min(0.4, worst * 0.5)
            reasons.append(f"{worst_tag} is trending toward its limit")

        # 2. service life
        years = years_since(eq.installed)
        if years is not None:
            risk += min(0.18, (years / 15.0) * 0.18)
            if years / 15.0 > 0.75:
                reasons.append(f"{years:.1f} years in service")

        # 3. carries the same instrument family that just failed
        if origin_sensor is not None and any(
            s.measurement == origin_sensor.measurement for s in eq.sensors
        ):
            risk += 0.12
            reasons.append(
                f"same {origin_sensor.measurement.value} instrumentation family as the failed point"
            )

        # 4. proximity
        if eq_id in direct:
            risk += 0.08
            reasons.append("directly connected to the incident origin")
        else:
            risk += 0.03

        if eq.criticality >= 2:
            risk += 0.06
            reasons.append(f"criticality class {eq.criticality}")
        if not reasons:
            reasons.append("shares a process path with the incident origin")

        bounded = max(0.05, min(0.92, risk))
        candidates.append(
            {
                "equipment_id": eq.id,
                "tag": eq.tag,
                "name": eq.name,
                "risk": round(bounded, 3),
                "reasons": reasons,
                "horizon": "next 30 days"
                if bounded > 0.5
                else "next quarter"
                if bounded > 0.3
                else "monitor",
            }
        )

    candidates.sort(key=lambda c: -c["risk"])
    return {
        "available": True,
        "incident_id": incident.id,
        "candidates": candidates[:limit],
        "caveat": (
            "Ranked from current telemetry, service age and topology — an early warning, "
            "not a guaranteed prediction."
        ),
    }
