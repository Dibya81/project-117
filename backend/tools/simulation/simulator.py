"""Trend fitting and threshold projection over observed telemetry.

This is a **statistical** simulator, not a physics one, and the distinction is
load-bearing. Nothing here models a compressor; it fits a line to measurements
that were actually recorded and reports where that line crosses a limit. Every
result carries the fit quality, the sample count and the assumptions, because
"the bearing fails on the 14th" and "a linear fit through 24 points with
r2=0.81 reaches the alarm limit in 11 days" are different claims and only the
second one is defensible.

Three refusals are deliberate:

* fewer than :data:`MIN_POINTS` samples returns ``usable: false`` rather than a
  slope through two points;
* a trend moving *away* from the threshold returns no crossing rather than a
  negative number of days;
* a poor fit is reported with ``confidence: "low"`` and the r2 that earned it,
  never smoothed into a clean-looking answer.

Pure stdlib: no numpy, so this runs in the API process without pulling a
numeric stack into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from backend.tools.base import ToolArgumentError

#: Below this, a trend line is arithmetic rather than evidence.
MIN_POINTS = 4

#: r2 at or above this is reported as a usable trend.
GOOD_FIT_R2 = 0.70
WEAK_FIT_R2 = 0.40

#: Projections beyond this are not returned - extrapolating a linear fit for
#: months is not a forecast, it is a straight line with a date on it.
MAX_HORIZON_HOURS = 24 * 90


@dataclass(frozen=True)
class Sample:
    """One observation: hours since the first sample, and its value."""

    hours: float
    value: float
    timestamp: datetime | None = None


@dataclass(frozen=True)
class Fit:
    slope_per_hour: float
    intercept: float
    r2: float
    points: int
    span_hours: float

    def at(self, hours: float) -> float:
        return self.intercept + self.slope_per_hour * hours

    def to_dict(self) -> dict[str, Any]:
        return {
            "slope_per_hour": round(self.slope_per_hour, 6),
            "slope_per_day": round(self.slope_per_hour * 24, 6),
            "intercept": round(self.intercept, 6),
            "r2": round(self.r2, 4),
            "points": self.points,
            "span_hours": round(self.span_hours, 2),
        }


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    normalised = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_series(
    points: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    value_key: str = "value",
    time_key: str = "timestamp",
) -> list[Sample]:
    """Normalise telemetry into ordered samples.

    Accepts the demo dataset's ``{"timestamp": ..., "value": ...}`` rows,
    two-element sequences, or bare numbers (treated as hourly). Rows whose
    value is not numeric are dropped rather than coerced to zero - a zero that
    was really a null moves a trend line.
    """
    raw: list[tuple[datetime | None, float, int]] = []
    for index, item in enumerate(points or []):
        stamp: datetime | None = None
        if isinstance(item, Mapping):
            stamp = _parse_timestamp(item.get(time_key))
            candidate = item.get(value_key)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            stamp = _parse_timestamp(item[0])
            candidate = item[1]
        else:
            candidate = item
        try:
            value = float(candidate)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        raw.append((stamp, value, index))

    if not raw:
        return []
    if all(stamp is not None for stamp, _, _ in raw):
        raw.sort(key=lambda row: row[0])  # type: ignore[arg-type,return-value]
        origin = raw[0][0]
        return [
            Sample(
                hours=(stamp - origin).total_seconds() / 3600.0,  # type: ignore[operator]
                value=value,
                timestamp=stamp,
            )
            for stamp, value, _ in raw
        ]
    # No usable timestamps: fall back to the given order at hourly spacing,
    # and say so through Sample.timestamp being None.
    raw.sort(key=lambda row: row[2])
    return [Sample(hours=float(i), value=value) for i, (_, value, _) in enumerate(raw)]


def linear_fit(samples: Sequence[Sample]) -> Fit:
    """Ordinary least squares on (hours, value)."""
    count = len(samples)
    if count < 2:
        raise ToolArgumentError("a trend needs at least two samples")
    xs = [s.hours for s in samples]
    ys = [s.value for s in samples]
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    if sxx == 0:
        raise ToolArgumentError(
            "every sample shares one timestamp; a trend over time is not defined"
        )
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    syy = sum((y - mean_y) ** 2 for y in ys)
    if syy == 0:
        r2 = 1.0  # a flat series is perfectly described by a flat line
    else:
        residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        r2 = max(0.0, 1.0 - residual / syy)
    return Fit(
        slope_per_hour=slope,
        intercept=intercept,
        r2=r2,
        points=count,
        span_hours=max(xs) - min(xs),
    )


def _confidence(fit: Fit) -> str:
    if fit.points < MIN_POINTS:
        return "insufficient_data"
    if fit.r2 >= GOOD_FIT_R2:
        return "medium"
    if fit.r2 >= WEAK_FIT_R2:
        return "low"
    return "very_low"


def describe_trend(
    points: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    value_key: str = "value",
    time_key: str = "timestamp",
) -> dict[str, Any]:
    """Fit a trend and describe it, including whether it should be trusted."""
    samples = parse_series(points, value_key=value_key, time_key=time_key)
    if len(samples) < 2:
        return {
            "usable": False,
            "points": len(samples),
            "reason": "fewer than two numeric samples were supplied",
            "method": "least_squares_linear",
        }
    fit = linear_fit(samples)
    first, last = samples[0].value, samples[-1].value
    change = last - first
    return {
        "usable": fit.points >= MIN_POINTS,
        "direction": "rising"
        if fit.slope_per_hour > 0
        else "falling"
        if fit.slope_per_hour < 0
        else "flat",
        "first_value": round(first, 4),
        "last_value": round(last, 4),
        "change": round(change, 4),
        "change_pct": round(change / first * 100, 2) if first else None,
        "min": round(min(s.value for s in samples), 4),
        "max": round(max(s.value for s in samples), 4),
        "mean": round(sum(s.value for s in samples) / fit.points, 4),
        "fit": fit.to_dict(),
        "confidence": _confidence(fit),
        "method": "least_squares_linear",
        "first_timestamp": samples[0].timestamp.isoformat() if samples[0].timestamp else None,
        "last_timestamp": samples[-1].timestamp.isoformat() if samples[-1].timestamp else None,
        "assumptions": [
            "the recent trend continues unchanged",
            "samples are comparable measurements of one signal",
            "no maintenance intervention occurs in the projection window",
        ],
        "caveat": (
            f"fewer than {MIN_POINTS} samples - reported for completeness, not for decisions"
            if fit.points < MIN_POINTS
            else ""
        ),
    }


def project(
    points: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    horizon_hours: float,
    value_key: str = "value",
    time_key: str = "timestamp",
) -> dict[str, Any]:
    """Project the fitted trend forward by ``horizon_hours``."""
    horizon = float(horizon_hours)
    if horizon <= 0:
        raise ToolArgumentError("horizon_hours must be positive")
    if horizon > MAX_HORIZON_HOURS:
        raise ToolArgumentError(
            f"horizon of {horizon:g}h exceeds the {MAX_HORIZON_HOURS}h limit; a linear "
            "fit projected that far is not a forecast"
        )
    samples = parse_series(points, value_key=value_key, time_key=time_key)
    if len(samples) < 2:
        raise ToolArgumentError("a projection needs at least two numeric samples")
    fit = linear_fit(samples)
    target_hours = samples[-1].hours + horizon
    projected = fit.at(target_hours)
    stamp = samples[-1].timestamp
    return {
        "projected_value": round(projected, 4),
        "horizon_hours": horizon,
        "horizon_days": round(horizon / 24, 2),
        "at": (stamp + timedelta(hours=horizon)).isoformat() if stamp else None,
        "from_value": round(samples[-1].value, 4),
        "fit": fit.to_dict(),
        "confidence": _confidence(fit),
        "method": "least_squares_linear_extrapolation",
        "extrapolation_ratio": (round(horizon / fit.span_hours, 2) if fit.span_hours > 0 else None),
        "caveat": (
            "the projection window is longer than the observed window, so this is "
            "an extrapolation well beyond the evidence"
            if fit.span_hours > 0 and horizon > fit.span_hours
            else ""
        ),
    }


def time_to_threshold(
    points: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    threshold: float,
    value_key: str = "value",
    time_key: str = "timestamp",
) -> dict[str, Any]:
    """When the fitted trend reaches ``threshold``.

    Returns ``crossing: null`` with a stated reason when the trend is flat,
    already past the limit, or moving away from it. Those are the three cases
    where a "days remaining" number would be fiction.
    """
    limit = float(threshold)
    samples = parse_series(points, value_key=value_key, time_key=time_key)
    if len(samples) < 2:
        return {
            "crossing": None,
            "reason": "fewer than two numeric samples were supplied",
            "method": "least_squares_linear",
            "usable": False,
        }
    fit = linear_fit(samples)
    current = samples[-1].value
    approaching_up = limit > current and fit.slope_per_hour > 0
    approaching_down = limit < current and fit.slope_per_hour < 0

    base = {
        "threshold": limit,
        "current_value": round(current, 4),
        "margin": round(limit - current, 4),
        "fit": fit.to_dict(),
        "confidence": _confidence(fit),
        "method": "least_squares_linear",
        "usable": fit.points >= MIN_POINTS,
        "assumptions": [
            "the fitted rate of change continues unchanged",
            "the threshold is the correct limit for this signal",
            "no intervention occurs before the crossing",
        ],
    }

    if (limit > current and fit.slope_per_hour <= 0) or (
        limit < current and fit.slope_per_hour >= 0
    ):
        return {
            **base,
            "crossing": None,
            "reason": (
                "the trend is flat or moving away from the threshold, so no "
                "crossing follows from this data"
            ),
        }
    if not (approaching_up or approaching_down):
        return {
            **base,
            "crossing": None,
            "reason": "the current value is already at or past the threshold",
            "already_exceeded": True,
        }

    hours = (limit - fit.intercept) / fit.slope_per_hour - samples[-1].hours
    if hours <= 0:
        return {
            **base,
            "crossing": None,
            "reason": "the fitted line places the crossing in the past",
        }
    stamp = samples[-1].timestamp
    return {
        **base,
        "crossing": {
            "hours": round(hours, 2),
            "days": round(hours / 24, 2),
            "at": (stamp + timedelta(hours=hours)).isoformat() if stamp else None,
        },
        "beyond_observed_window": fit.span_hours > 0 and hours > fit.span_hours,
        "caveat": (
            "the crossing is further ahead than the observed window is long; treat "
            "it as a screening indication, not a due date"
            if fit.span_hours > 0 and hours > fit.span_hours
            else ""
        ),
    }


__all__ = [
    "GOOD_FIT_R2",
    "MAX_HORIZON_HOURS",
    "MIN_POINTS",
    "WEAK_FIT_R2",
    "Fit",
    "Sample",
    "describe_trend",
    "linear_fit",
    "parse_series",
    "project",
    "time_to_threshold",
]
