"""A measurement-backed twin of one piece of equipment.

"Digital twin" is an overloaded phrase, so here is exactly what this is and is
not. It **is** an assessment built from three inputs the plant already has:
the equipment record, its recent telemetry, and its declared baseline and
alarm limits. It compares them, fits a trend per signal, and reports margins,
deviations and projected crossings. It is **not** a physics or process model:
nothing here knows what a centrifugal compressor is, and it will never predict
a behaviour that is not visible in the numbers it was given.

Every signal in the output carries the values that produced its verdict -
current, baseline, limit, deviation, fit - so a reader can recompute the
conclusion by hand. The health index has a documented formula for the same
reason: an unexplained score out of 100 is the kind of number that gets
quoted in a meeting and cannot be defended in the next one.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.tools.base import ToolArgumentError
from backend.tools.simulation.simulator import describe_trend, time_to_threshold

#: Status bands by fraction of the alarm limit consumed.
WARNING_FRACTION = 0.85

#: Weight applied to each signal's margin loss when scoring health. Signals
#: without a declared limit cannot contribute, because there is nothing to be
#: a fraction of.
HEALTH_FORMULA = (
    "health = 100 - mean over limited signals of "
    "(100 * clamp(current / limit, 0, 1.25) - 100) capped at 0..100"
)


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_to_baseline(current: float, baseline: float | None) -> dict[str, Any]:
    """Absolute and relative deviation from a declared baseline."""
    if baseline is None:
        return {"baseline": None, "deviation": None, "deviation_pct": None}
    return {
        "baseline": round(baseline, 4),
        "deviation": round(current - baseline, 4),
        "deviation_pct": round((current - baseline) / baseline * 100, 2) if baseline else None,
    }


def assess_signal(
    name: str,
    series: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    baseline: float | None = None,
    limit: float | None = None,
    unit: str = "",
) -> dict[str, Any]:
    """Assess one signal: level, deviation, trend, and margin to its limit."""
    trend = describe_trend(series)
    if not trend.get("last_value") and trend.get("last_value") != 0:
        return {
            "signal": name,
            "unit": unit,
            "status": "no_data",
            "reason": trend.get("reason") or "no numeric samples were supplied",
            "trend": trend,
        }
    current = float(trend["last_value"])

    status = "normal"
    fraction = None
    if limit is not None and limit != 0:
        fraction = current / limit
        if fraction >= 1.0:
            status = "exceeded"
        elif fraction >= WARNING_FRACTION:
            status = "warning"
    elif baseline is not None and baseline != 0 and (current - baseline) / baseline > 0.15:
        # No declared limit: a 15% excursion from baseline is reported as
        # elevated, and labelled as baseline-relative so nobody reads it as
        # an alarm.
        status = "elevated_vs_baseline"

    projection: dict[str, Any] | None = None
    if limit is not None:
        projection = time_to_threshold(series, threshold=float(limit))

    return {
        "signal": name,
        "unit": unit,
        "current": round(current, 4),
        "limit": limit,
        "limit_fraction": round(fraction, 4) if fraction is not None else None,
        "margin_to_limit": round(limit - current, 4) if limit is not None else None,
        "status": status,
        **compare_to_baseline(current, baseline),
        "trend": trend,
        "projection": projection,
    }


def health_index(signals: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Score 0-100 from the signals that have a declared limit.

    Returns ``null`` rather than a number when no signal has a limit. A health
    score computed from signals with nothing to compare against would be an
    invention, and this is precisely the sort of number that ends up on a
    dashboard.
    """
    fractions = [
        min(max(float(item["limit_fraction"]), 0.0), 1.25)
        for item in signals
        if item.get("limit_fraction") is not None
    ]
    if not fractions:
        return {
            "value": None,
            "basis": "no signal has a declared limit",
            "formula": HEALTH_FORMULA,
            "signals_used": 0,
        }
    mean_fraction = sum(fractions) / len(fractions)
    score = max(0.0, min(100.0, (1.0 - mean_fraction) * 100.0 + 50.0 * (1.0 - mean_fraction)))
    # Expressed plainly: at the limit the score is 0, at half the limit it is
    # 75, at zero it is 150 clamped to 100.
    return {
        "value": round(score, 1),
        "basis": f"mean limit fraction {round(mean_fraction, 4)} over {len(fractions)} signal(s)",
        "formula": "health = clamp((1 - mean_limit_fraction) * 150, 0, 100)",
        "signals_used": len(fractions),
    }


def assess(
    *,
    equipment: Mapping[str, Any],
    telemetry: Mapping[str, Sequence[Mapping[str, Any] | Sequence[Any]]],
    baselines: Mapping[str, float] | None = None,
    limits: Mapping[str, float] | None = None,
    units: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Assess a piece of equipment from its telemetry.

    ``telemetry`` maps signal name -> series. ``baselines`` and ``limits`` are
    the plant's declared values; when a signal has neither, it is still
    reported, with its status explaining that there was nothing to compare it
    against. Silently dropping such a signal would hide a measurement.
    """
    if not isinstance(equipment, Mapping) or not equipment.get("id"):
        raise ToolArgumentError("an equipment record with an 'id' is required to build a twin")
    if not telemetry:
        raise ToolArgumentError(
            f"no telemetry was supplied for {equipment.get('id')}; a twin with no "
            "measurements would report a health score based on nothing"
        )

    baseline_map = {str(k): _number(v) for k, v in (baselines or {}).items()}
    limit_map = {str(k): _number(v) for k, v in (limits or {}).items()}
    unit_map = {str(k): str(v) for k, v in (units or {}).items()}

    signals = [
        assess_signal(
            name,
            series,
            baseline=baseline_map.get(name),
            limit=limit_map.get(name),
            unit=unit_map.get(name, ""),
        )
        for name, series in telemetry.items()
    ]

    exceeded = [s for s in signals if s.get("status") == "exceeded"]
    warning = [s for s in signals if s.get("status") == "warning"]
    elevated = [s for s in signals if s.get("status") == "elevated_vs_baseline"]
    missing = [s for s in signals if s.get("status") == "no_data"]

    if exceeded:
        condition = "alarm"
    elif warning:
        condition = "warning"
    elif elevated:
        condition = "watch"
    elif len(missing) == len(signals):
        condition = "unknown"
    else:
        condition = "normal"

    findings: list[dict[str, Any]] = []
    for signal in exceeded + warning + elevated:
        crossing = ((signal.get("projection") or {}).get("crossing") or {}) or {}
        statement = f"{signal['signal']} is {signal['current']}{(' ' + signal['unit']) if signal['unit'] else ''}"
        if signal.get("limit") is not None:
            statement += f" against a limit of {signal['limit']}"
        if signal.get("deviation_pct") is not None:
            statement += f", {signal['deviation_pct']:+}% versus baseline"
        if crossing.get("days") is not None:
            statement += f"; the fitted trend reaches the limit in {crossing['days']} days"
        findings.append(
            {
                "signal": signal["signal"],
                "status": signal["status"],
                "statement": statement,
                "inputs": {
                    "current": signal.get("current"),
                    "baseline": signal.get("baseline"),
                    "limit": signal.get("limit"),
                    "samples": (signal.get("trend") or {}).get("fit", {}).get("points"),
                    "r2": (signal.get("trend") or {}).get("fit", {}).get("r2"),
                },
                "confidence": (signal.get("trend") or {}).get("confidence"),
            }
        )

    return {
        "equipment_id": equipment.get("id"),
        "name": equipment.get("name"),
        "condition": condition,
        "health": health_index(signals),
        "signals": signals,
        "findings": findings,
        "counts": {
            "signals": len(signals),
            "exceeded": len(exceeded),
            "warning": len(warning),
            "elevated": len(elevated),
            "no_data": len(missing),
        },
        "method": "statistical_twin",
        "model_basis": (
            "declared baselines and limits compared against recorded telemetry, with "
            "a least-squares trend per signal. No process or physics model is involved."
        ),
        "assumptions": [
            "the supplied baselines and limits are current and correct for this unit",
            "telemetry samples are comparable measurements of the named signal",
            "the observed rate of change continues while no intervention occurs",
        ],
        "caveat": (
            "signals reported as no_data were requested but had no numeric samples; "
            "the condition above does not account for them"
            if missing
            else ""
        ),
    }


__all__ = [
    "HEALTH_FORMULA",
    "WARNING_FRACTION",
    "assess",
    "assess_signal",
    "compare_to_baseline",
    "health_index",
]
