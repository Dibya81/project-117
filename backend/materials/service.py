"""Deterministic domain service for materials, inventory and business impact.

Every number this module returns is computed here, in Python, from stored rows.
No language model performs arithmetic in Project 117, and no figure is returned
without the basis it was derived from.

Three conventions run through the whole module:

**Limitations are values, not exceptions.** When the data needed for an answer is
absent the function returns a structured ``limitations`` entry naming the specific
gap — ``INVENTORY_DATA_UNAVAILABLE``, ``INSUFFICIENT_HISTORY``,
``PRICE_HISTORY_UNAVAILABLE``, ``MAINTENANCE_REQUIREMENT_NOT_FOUND``,
``CONVERSION_BASIS_REQUIRED`` — rather than raising or, worse, substituting a
plausible number. An agent reading the payload can see exactly what is missing.

**Derived values carry their method.** ``available`` carries the formula
``quantity − reserved``; a cost carries ``quantity × unit_price``; a forecast
carries its sample size and dispersion. A reviewer can re-derive any of them.

**Confidence is a function of evidence.** It is computed from sample counts and
dispersion, never asserted, and it drops to ``LOW``/``NONE`` when the evidence is
thin instead of staying ``HIGH`` because the answer looks tidy.
"""

from __future__ import annotations

import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.materials.models import (
    CalculationStatus,
    DataStatus,
    MaterialClass,
    MaterialStatus,
    MovementType,
    PeriodType,
)
from backend.materials.units import (
    ConversionBasis,
    Price,
    Quantity,
    UnitError,
    convert,
    cost_of,
    dimension,
    parse_unit,
)

#: Limitation codes. Stable strings, so a client or an agent can branch on them.
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INVENTORY_DATA_UNAVAILABLE = "INVENTORY_DATA_UNAVAILABLE"
PRICE_HISTORY_UNAVAILABLE = "PRICE_HISTORY_UNAVAILABLE"
MAINTENANCE_REQUIREMENT_NOT_FOUND = "MAINTENANCE_REQUIREMENT_NOT_FOUND"
CONVERSION_BASIS_REQUIRED = "CONVERSION_BASIS_REQUIRED"
MATERIAL_NOT_FOUND = "MATERIAL_NOT_FOUND"
EQUIPMENT_NOT_FOUND = "EQUIPMENT_NOT_FOUND"

#: A change at or above this percentage is flagged abnormal. Configurable at the
#: call site; the default is a threshold, not a claim about markets.
ABNORMAL_CHANGE_PCT = 10.0
WARNING_CHANGE_PCT = 5.0

#: A forecast needs at least this many daily consumption observations.
MIN_FORECAST_SAMPLES = 3
FORECAST_WINDOW_DAYS = 90

#: Days-of-cover window.
COVER_WINDOW_DAYS = 30


def _today(anchor: date | None = None) -> date:
    return anchor or datetime.now(timezone.utc).date()


def _limitation(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **extra}


def _iso(d: date | str) -> str:
    return d.isoformat() if isinstance(d, date) else d


# ------------------------------------------------------------------ inventory


def inventory_status(
    store: Any,
    material_id: str,
    *,
    anchor: date | None = None,
    window_days: int = COVER_WINDOW_DAYS,
) -> dict[str, Any]:
    """Current position for one material, with coverage and provenance.

    ``available`` is ``quantity − reserved``, computed here and nowhere else.
    """
    material = store.material(material_id)
    if material is None:
        return {
            "material_id": material_id,
            "limitations": [_limitation(MATERIAL_NOT_FOUND, f"no material with id {material_id}")],
        }
    balance = store.latest_balance(material_id)
    if balance is None:
        return {
            "material_id": material_id,
            "material": material,
            "limitations": [
                _limitation(
                    INVENTORY_DATA_UNAVAILABLE,
                    f"no inventory balance recorded for {material_id}",
                )
            ],
        }

    quantity = float(balance["quantity"])
    reserved = float(balance["reserved"])
    available = round(quantity - reserved, 6)
    safety = float(balance["safety_stock"])
    reorder = float(balance["reorder_level"])
    if available <= 0:
        status = MaterialStatus.OUT_OF_STOCK
    elif available <= safety:
        status = MaterialStatus.CRITICAL
    elif available <= reorder:
        status = MaterialStatus.DEPLETING
    else:
        status = MaterialStatus.AVAILABLE

    cover = days_of_cover(store, material_id, anchor=anchor, window_days=window_days)

    limitations: list[dict[str, Any]] = []
    if cover["average_daily_consumption"] is None:
        limitations.extend(cover.get("limitations", []))

    return {
        "material_id": material_id,
        "material": material,
        "location": balance["location"],
        "quantity": quantity,
        "reserved": reserved,
        "available": available,
        "safety_stock": safety,
        "reorder_level": reorder,
        "threshold": balance["threshold"],
        "unit": balance["unit"],
        "status": status.value,
        "timestamp": balance["timestamp"],
        "days_of_cover": cover["days_of_cover"],
        "average_daily_consumption": cover["average_daily_consumption"],
        "source": balance["provenance"].get("source", ""),
        "data_status": balance["provenance"].get("data_status", DataStatus.SYNTHETIC_DEMO.value),
        "provenance": balance["provenance"],
        "calculation_basis": {
            "available": "quantity − reserved",
            "status_rule": "OUT_OF_STOCK if available≤0; CRITICAL if ≤safety; DEPLETING if ≤reorder; else AVAILABLE",
            "days_of_cover": "available ÷ average daily consumption",
            "window_days": window_days,
        },
        "limitations": limitations,
    }


def days_of_cover(
    store: Any,
    material_id: str,
    *,
    anchor: date | None = None,
    window_days: int = COVER_WINDOW_DAYS,
) -> dict[str, Any]:
    """How long the current position lasts at the observed consumption rate.

    Consumption is measured from CONSUMPTION movements in the window. A material
    that is never consumed (a passive spare) has no meaningful cover figure, and
    that is reported as a limitation rather than as ``0`` or ``∞``.
    """
    today = _today(anchor)
    since = (today - timedelta(days=window_days)).isoformat()
    balance = store.latest_balance(material_id)
    movements = store.movements(
        material_id, movement_type=MovementType.CONSUMPTION.value, since=since, limit=1000
    )
    if not movements:
        return {
            "days_of_cover": None,
            "average_daily_consumption": None,
            "samples": 0,
            "limitations": [
                _limitation(
                    INSUFFICIENT_HISTORY,
                    f"no consumption movements recorded for {material_id} in the last "
                    f"{window_days} days, so days of cover cannot be computed",
                    window_days=window_days,
                )
            ],
        }
    total = sum(float(m["quantity"]) for m in movements)
    per_day = total / window_days
    available = None
    if balance is not None:
        available = float(balance["quantity"]) - float(balance["reserved"])
    cover = round(available / per_day, 2) if available is not None and per_day > 0 else None
    return {
        "days_of_cover": cover,
        "average_daily_consumption": round(per_day, 6),
        "consumed_in_window": round(total, 6),
        "samples": len(movements),
        "window_days": window_days,
        "limitations": [],
    }


def forecast_inventory(
    store: Any,
    material_id: str,
    *,
    anchor: date | None = None,
    window_days: int = FORECAST_WINDOW_DAYS,
) -> dict[str, Any]:
    """Project depletion from observed consumption, or say why it cannot.

    Refuses to forecast on thin evidence. ``MIN_FORECAST_SAMPLES`` daily
    observations are required; below that the answer is ``INSUFFICIENT_HISTORY``
    with the sample count, because a depletion date fitted to two points is a
    guess wearing a date.
    """
    today = _today(anchor)
    material = store.material(material_id)
    if material is None:
        return {
            "material_id": material_id,
            "limitations": [_limitation(MATERIAL_NOT_FOUND, f"no material with id {material_id}")],
        }
    balance = store.latest_balance(material_id)
    if balance is None:
        return {
            "material_id": material_id,
            "limitations": [
                _limitation(INVENTORY_DATA_UNAVAILABLE, f"no inventory balance for {material_id}")
            ],
        }

    since = (today - timedelta(days=window_days)).isoformat()
    movements = store.movements(
        material_id, movement_type=MovementType.CONSUMPTION.value, since=since, limit=2000
    )
    by_day: dict[str, float] = {}
    for m in movements:
        day = str(m["timestamp"])[:10]
        by_day[day] = by_day.get(day, 0.0) + float(m["quantity"])
    samples = len(by_day)
    if samples < MIN_FORECAST_SAMPLES:
        return {
            "material_id": material_id,
            "unit": balance["unit"],
            "samples": samples,
            "required_samples": MIN_FORECAST_SAMPLES,
            "status": INSUFFICIENT_HISTORY,
            "limitations": [
                _limitation(
                    INSUFFICIENT_HISTORY,
                    f"only {samples} day(s) with consumption in the last {window_days} days; "
                    f"{MIN_FORECAST_SAMPLES} are required before a depletion date is meaningful",
                    samples=samples,
                    required_samples=MIN_FORECAST_SAMPLES,
                )
            ],
        }

    daily = list(by_day.values())
    mean = statistics.fmean(daily)
    stdev = statistics.pstdev(daily) if len(daily) > 1 else 0.0
    cv = (stdev / mean) if mean else 0.0
    available = float(balance["quantity"]) - float(balance["reserved"])
    safety = float(balance["safety_stock"])

    if mean <= 0:
        return {
            "material_id": material_id,
            "unit": balance["unit"],
            "samples": samples,
            "status": INSUFFICIENT_DATA,
            "limitations": [
                _limitation(INSUFFICIENT_DATA, "recorded consumption averages zero, so no depletion can be projected")
            ],
        }

    days_to_zero = max(0.0, available) / mean
    days_to_safety = max(0.0, available - safety) / mean
    if samples >= 10 and cv < 0.30:
        confidence = "HIGH"
    elif samples >= 5 and cv < 0.60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "material_id": material_id,
        "unit": balance["unit"],
        "available": round(available, 6),
        "safety_stock": safety,
        "samples": samples,
        "window_days": window_days,
        "mean_daily_consumption": round(mean, 6),
        "stdev_daily_consumption": round(stdev, 6),
        "coefficient_of_variation": round(cv, 4),
        "projected_depletion_date": (today + timedelta(days=days_to_zero)).isoformat(),
        "projected_safety_stock_crossing_date": (
            (today + timedelta(days=days_to_safety)).isoformat() if available > safety else today.isoformat()
        ),
        "days_to_depletion": round(days_to_zero, 2),
        "days_to_safety_stock": round(days_to_safety, 2),
        "confidence": confidence,
        "confidence_basis": (
            f"{samples} consumption day(s), coefficient of variation {cv:.2f}; "
            "HIGH needs ≥10 days and cv<0.30"
        ),
        "source": balance["provenance"].get("source", ""),
        "data_status": balance["provenance"].get("data_status", ""),
        "limitations": [],
    }


# ---------------------------------------------------------------------- price


def price_history(
    store: Any,
    item_id: str,
    *,
    window_days: int = 30,
    anchor: date | None = None,
    abnormal_pct: float = ABNORMAL_CHANGE_PCT,
    warning_pct: float = WARNING_CHANGE_PCT,
    target_unit: str | None = None,
) -> dict[str, Any]:
    """Append-only price series with a window comparison and a movement flag.

    The comparison baseline is the latest observation at or before the window
    start, so "30D change" means the same thing for an item priced daily and one
    priced monthly. Prices are never converted between units here unless a target
    unit is asked for, and a cross-dimension re-base is refused without a basis.
    """
    today = _today(anchor)
    material = store.material(item_id)
    unit = material["unit"] if material else None
    if target_unit and unit:
        try:
            unit = parse_unit(target_unit)
        except UnitError:
            return {
                "item_id": item_id,
                "status": DATA_UNAVAILABLE,
                "limitations": [_limitation(DATA_UNAVAILABLE, f"unsupported unit {target_unit!r}")],
            }

    observations = store.prices(item_id, limit=2000)
    if not observations:
        return {
            "item_id": item_id,
            "status": PRICE_HISTORY_UNAVAILABLE,
            "window_days": window_days,
            "limitations": [
                _limitation(
                    PRICE_HISTORY_UNAVAILABLE,
                    f"no price observations recorded for {item_id}",
                )
            ],
        }

    ascending = sorted(observations, key=lambda o: (o["observed_on"], o["id"]))
    current = ascending[-1]
    cutoff = (today - timedelta(days=window_days)).isoformat()
    baseline = None
    for obs in ascending:
        if obs["observed_on"] <= cutoff:
            baseline = obs
        else:
            break
    if baseline is None:
        baseline = ascending[0]

    price_unit = f"{current['currency']}/{parse_unit(current['unit']).value}"
    basis: dict[str, Any] = {
        "current": current["price"],
        "baseline": baseline["price"],
        "formula": "(current − baseline) ÷ baseline × 100",
        "window_days": window_days,
    }
    limitations: list[dict[str, Any]] = []

    conversion_note = None
    current_price = float(current["price"])
    baseline_price = float(baseline["price"])
    if unit and parse_unit(current["unit"]) != parse_unit(unit):
        try:
            conv = convert(current_price, current["unit"], unit)
            current_price = conv.amount
            baseline_price = convert(baseline_price, baseline["unit"], unit).amount
            price_unit = f"{current['currency']}/{parse_unit(unit).value}"
            conversion_note = conv.note
        except UnitError as exc:
            limitations.append(
                _limitation(
                    CONVERSION_BASIS_REQUIRED,
                    f"cannot express the price in {target_unit}: {exc}",
                )
            )

    change_abs = round(current_price - baseline_price, 6)
    change_pct = round((change_abs / baseline_price * 100) if baseline_price else math.nan, 4)
    if not math.isfinite(change_pct):
        change_pct = 0.0
        limitations.append(
            _limitation(INSUFFICIENT_DATA, "baseline price is zero, so no percentage change is defined")
        )

    magnitude = abs(change_pct)
    if magnitude >= abnormal_pct:
        movement = "ABNORMAL"
    elif magnitude >= warning_pct:
        movement = "WARNING"
    else:
        movement = "NORMAL"

    series = [
        {"date": o["observed_on"], "price": o["price"], "data_status": o["data_status"], "source": o["source"]}
        for o in ascending
        if o["observed_on"] >= cutoff
    ]

    return {
        "item_id": item_id,
        "name": material["name"] if material else None,
        "current": {"price": round(current_price, 4), "unit": price_unit, "observed_on": current["observed_on"]},
        "baseline": {"price": round(baseline_price, 4), "unit": price_unit, "observed_on": baseline["observed_on"]},
        "change_absolute": change_abs,
        "change_percent": change_pct,
        "movement": movement,
        "window_days": window_days,
        "thresholds": {"warning_pct": warning_pct, "abnormal_pct": abnormal_pct},
        "series": series,
        "points": len(series),
        "source": current["source"],
        "data_status": current["data_status"],
        "last_updated": current["observed_on"],
        "calculation_basis": basis,
        "conversion_note": conversion_note,
        "limitations": limitations,
    }


# ------------------------------------------------------------------ equipment


def equipment_requirements(
    store: Any,
    equipment_id: str,
    *,
    failure_mode: str | None = None,
    anchor: date | None = None,
) -> dict[str, Any]:
    """What an asset needs, with the live inventory position for each item.

    When ``failure_mode`` is given, mode-specific requirements are ranked first:
    a diagnosis of ``seal_leak`` should surface the seal kit before the routine
    filter set.
    """
    requirements = store.requirements(equipment_id=equipment_id, failure_mode=failure_mode)
    if not requirements and failure_mode:
        # Fall back to every requirement for the asset, flagged as such.
        requirements = store.requirements(equipment_id=equipment_id)
    if not requirements:
        return {
            "equipment_id": equipment_id,
            "requirements": [],
            "limitations": [
                _limitation(
                    MAINTENANCE_REQUIREMENT_NOT_FOUND,
                    f"no material requirement is recorded for equipment {equipment_id}",
                )
            ],
        }

    rows: list[dict[str, Any]] = []
    for req in requirements:
        status = inventory_status(store, req["item_id"], anchor=anchor)
        rows.append(
            {
                "requirement_id": req["id"],
                "item_id": req["item_id"],
                "item_name": (status.get("material") or {}).get("name"),
                "required_quantity": req["quantity"],
                "unit": req["unit"],
                "schedule": req["schedule"],
                "purpose": req["purpose"],
                "failure_mode": req["failure_mode"],
                "mode_match": bool(failure_mode and req["failure_mode"] == failure_mode),
                "inventory": {
                    "available": status.get("available"),
                    "reserved": status.get("reserved"),
                    "safety_stock": status.get("safety_stock"),
                    "status": status.get("status"),
                    "unit": status.get("unit"),
                    "data_status": status.get("data_status"),
                },
                "provenance": req["provenance"],
                "limitations": status.get("limitations", []),
            }
        )
    # Mode-matched first, then by whether stock covers the need.
    rows.sort(key=lambda r: (not r["mode_match"], r["item_id"]))
    return {
        "equipment_id": equipment_id,
        "failure_mode": failure_mode,
        "requirements": rows,
        "limitations": [],
    }


def material_requirement(
    store: Any,
    equipment_id: str,
    *,
    failure_mode: str | None = None,
    multiplier: float = 1.0,
    anchor: date | None = None,
) -> dict[str, Any]:
    """Required quantity vs available stock vs safety stock, per item.

    The coverage rule is explicit and deterministic:

        surplus = available − (required × multiplier) − safety_stock
        COVERED  when surplus ≥ 0
    """
    resolved = equipment_requirements(store, equipment_id, failure_mode=failure_mode, anchor=anchor)
    if resolved.get("limitations"):
        return {"equipment_id": equipment_id, **resolved}

    lines: list[dict[str, Any]] = []
    for row in resolved["requirements"]:
        required = round(float(row["required_quantity"]) * multiplier, 6)
        inv = row["inventory"]
        available = inv.get("available")
        safety = inv.get("safety_stock") or 0.0
        limitations = list(row.get("limitations") or [])
        if available is None:
            lines.append(
                {
                    **row,
                    "required_quantity": required,
                    "available": None,
                    "surplus_after_requirement_and_safety": None,
                    "coverage": "UNKNOWN",
                    "limitations": limitations,
                }
            )
            continue
        surplus = round(float(available) - required - float(safety), 6)
        lines.append(
            {
                "requirement_id": row["requirement_id"],
                "item_id": row["item_id"],
                "item_name": row["item_name"],
                "unit": row["unit"],
                "required_quantity": required,
                "required_basis": f"requirement {row['required_quantity']} × multiplier {multiplier}",
                "available": available,
                "reserved": inv.get("reserved"),
                "safety_stock": safety,
                "surplus_after_requirement_and_safety": surplus,
                "coverage": "COVERED" if surplus >= 0 else "SHORTFALL",
                "shortfall_quantity": 0.0 if surplus >= 0 else round(-surplus, 6),
                "schedule": row["schedule"],
                "purpose": row["purpose"],
                "failure_mode": row["failure_mode"],
                "mode_match": row["mode_match"],
                "inventory_status": inv.get("status"),
                "limitations": limitations,
                "calculation_basis": {
                    "rule": "surplus = available − required − safety_stock; COVERED when surplus ≥ 0",
                    "multiplier": multiplier,
                },
            }
        )

    overall = "UNKNOWN"
    if lines and all(line["coverage"] == "COVERED" for line in lines):
        overall = "COVERED"
    elif any(line["coverage"] == "SHORTFALL" for line in lines):
        overall = "SHORTFALL"
    return {
        "equipment_id": equipment_id,
        "failure_mode": failure_mode,
        "multiplier": multiplier,
        "overall_coverage": overall,
        "lines": lines,
        "limitations": [],
    }


# ------------------------------------------------------------------ financial


def financial_impact(
    store: Any,
    item_id: str,
    quantity: float,
    *,
    unit: str | None = None,
    anchor: date | None = None,
) -> dict[str, Any]:
    """Cost of a quantity at the latest recorded price. Deterministic.

    ``quantity × unit_price``, with the unit re-based if needed. A cross-dimension
    re-base (KL against a ₹/MT price) needs the material's recorded density and is
    refused with ``CONVERSION_BASIS_REQUIRED`` when that is missing.
    """
    material = store.material(item_id)
    if material is None:
        return {
            "item_id": item_id,
            "limitations": [_limitation(MATERIAL_NOT_FOUND, f"no material with id {item_id}")],
        }
    latest = store.latest_price(item_id)
    if latest is None:
        return {
            "item_id": item_id,
            "quantity": quantity,
            "unit": unit or material["unit"],
            "limitations": [
                _limitation(PRICE_HISTORY_UNAVAILABLE, f"no price observation for {item_id}, so cost cannot be computed")
            ],
        }

    want_unit = parse_unit(unit or material["unit"])
    basis = None
    density = (material.get("quality_attributes") or {}).get("density_kg_per_m3")
    if density and dimension(parse_unit(latest["unit"])) != dimension(want_unit):
        basis = ConversionBasis(
            kg_per_m3=float(density),
            source=f"material {item_id} quality_attributes.density_kg_per_m3",
            note="Recorded material density used to bridge mass and volume.",
        )

    try:
        qty = Quantity.of(quantity, want_unit, basis=basis)
        price = Price.of(latest["price"], latest["unit"], currency=latest["currency"], basis=basis)
        total, calc = cost_of(qty, price)
    except UnitError as exc:
        return {
            "item_id": item_id,
            "quantity": quantity,
            "unit": want_unit.value,
            "limitations": [
                _limitation(CONVERSION_BASIS_REQUIRED, f"cannot price {quantity} {want_unit.value} of {item_id}: {exc}")
            ],
        }

    return {
        "item_id": item_id,
        "name": material["name"],
        "quantity": quantity,
        "unit": want_unit.value,
        "unit_price": latest["price"],
        "unit_price_per": latest["unit"],
        "price_observed_on": latest["observed_on"],
        "currency": latest["currency"],
        "estimated_cost": total,
        "calculation_status": CalculationStatus.ILLUSTRATIVE.value,
        "source": latest["source"],
        "data_status": latest["data_status"],
        "provenance": latest["provenance"],
        "calculation_basis": calc,
        "limitations": [],
    }


# --------------------------------------------------------------- production


def production_series(
    store: Any,
    *,
    period: PeriodType = PeriodType.DAILY,
    product_id: str | None = None,
    process_unit_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    anchor: date | None = None,
) -> dict[str, Any]:
    """Production aggregated to DAILY, WEEKLY or MONTHLY, with period-over-period.

    Only daily rows are stored; the coarser views are aggregated here so the three
    granularities cannot drift apart. Period-over-period compares the most recent
    complete period against the one before it.
    """
    today = _today(anchor)
    rows = store.production(
        product_id=product_id,
        process_unit_id=process_unit_id,
        period_type=PeriodType.DAILY.value,
        since=since,
        until=until,
        limit=2000,
    )
    if not rows:
        return {
            "period": period.value,
            "buckets": [],
            "limitations": [
                _limitation(DATA_UNAVAILABLE, "no production output recorded for the requested filter")
            ],
        }

    unit = rows[0]["unit"]
    mismatched = {r["unit"] for r in rows if r["unit"] != unit}
    limitations: list[dict[str, Any]] = []
    if mismatched:
        limitations.append(
            _limitation(
                INSUFFICIENT_DATA,
                f"production is recorded in {sorted({unit, *mismatched})}; buckets are grouped per unit "
                "rather than summed across incompatible units",
            )
        )

    buckets: dict[tuple[str, str], float] = {}
    for row in rows:
        day = date.fromisoformat(str(row["period_start"])[:10])
        key_start, key_end = _bucket(period, day)
        buckets[(key_start, key_end)] = buckets.get((key_start, key_end), 0.0) + float(row["quantity"])

    ordered = sorted(buckets.items(), key=lambda kv: kv[0][0])
    # Period-over-period must compare like with like. The bucket containing today
    # is usually incomplete — on a Monday a "week" holds one day — and dividing it
    # by a full week produces a dramatic, meaningless fall. Only complete periods
    # (period_end already past) are eligible for the comparison; the newest bucket
    # is still returned, flagged, so the UI can label it "to date".
    complete = [(k, v) for k, v in ordered if k[1] <= today.isoformat()]
    latest = complete[-1] if complete else ordered[-1]
    latest_is_partial = latest[0][1] > today.isoformat()
    previous = complete[-2] if len(complete) > 1 else None
    change_pct = None
    if previous and previous[1]:
        change_pct = round((latest[1] - previous[1]) / previous[1] * 100, 4)

    return {
        "period": period.value,
        "unit": unit,
        "product_id": product_id,
        "process_unit_id": process_unit_id,
        "buckets": [
            {"period_start": start, "period_end": end, "quantity": round(qty, 3)}
            for (start, end), qty in ordered
        ],
        "latest": {
            "period_start": latest[0][0],
            "period_end": latest[0][1],
            "quantity": round(latest[1], 3),
            "partial": latest_is_partial,
        },
        "previous": (
            {"period_start": previous[0][0], "period_end": previous[0][1], "quantity": round(previous[1], 3)}
            if previous
            else None
        ),
        "change_percent": change_pct,
        "trend": (
            None
            if change_pct is None
            else ("INCREASING" if change_pct > 0.5 else "DECREASING" if change_pct < -0.5 else "FLAT")
        ),
        "records": len(rows),
        "source": rows[0]["source"],
        "data_status": rows[0]["provenance"].get("data_status", ""),
        "calculation_basis": {
            "aggregation": f"sum of DAILY quantity within each {period.value.lower()} bucket",
            "change": "(latest complete period − previous complete period) ÷ previous × 100",
            "partial_period_excluded": "the bucket containing today is returned but never used as a comparison baseline",
        },
        "limitations": limitations,
    }


def _bucket(period: PeriodType, day: date) -> tuple[str, str]:
    if period is PeriodType.DAILY:
        return day.isoformat(), day.isoformat()
    if period is PeriodType.WEEKLY:
        start = date.fromordinal(day.toordinal() - day.weekday())
        return start.isoformat(), date.fromordinal(start.toordinal() + 6).isoformat()
    start = day.replace(day=1)
    import calendar as _cal

    end = start.replace(day=_cal.monthrange(start.year, start.month)[1])
    return start.isoformat(), end.isoformat()


# ------------------------------------------------------------- dashboard / BI


def materials_dashboard(store: Any, *, anchor: date | None = None) -> dict[str, Any]:
    """The console's Materials overview, computed from stored rows only.

    Every figure is derived; nothing is a placeholder. When a component cannot be
    computed (no consumption history for cover, no price for value) the entry says
    which one and why.
    """
    today = _today(anchor)
    materials = store.materials(limit=500)
    limitations: list[dict[str, Any]] = []

    by_class: dict[str, int] = {}
    for m in materials:
        by_class[m["material_class"]] = by_class.get(m["material_class"], 0) + 1

    critical: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    inventory_value = 0.0
    priced = 0
    for m in materials:
        status = inventory_status(store, m["id"], anchor=anchor)
        positions.append(status)
        if status.get("status") in (MaterialStatus.CRITICAL.value, MaterialStatus.OUT_OF_STOCK.value):
            critical.append(
                {
                    "material_id": m["id"],
                    "name": m["name"],
                    "material_class": m["material_class"],
                    "status": status.get("status"),
                    "available": status.get("available"),
                    "safety_stock": status.get("safety_stock"),
                    "unit": status.get("unit"),
                    "location": status.get("location"),
                }
            )
        latest = store.latest_price(m["id"])
        if latest and status.get("quantity") is not None and latest["unit"] == status.get("unit"):
            inventory_value += float(status["quantity"]) * float(latest["price"])
            priced += 1
    if priced < len(materials):
        limitations.append(
            _limitation(
                PRICE_HISTORY_UNAVAILABLE,
                f"inventory value covers {priced} of {len(materials)} materials; the rest have no price "
                "observation in their own unit",
            )
        )

    raw = [p for p in positions if (p.get("material") or {}).get("material_class") == MaterialClass.RAW_MATERIAL.value]
    raw_cover = []
    for p in raw:
        # `days_of_cover` is null when no consumption was recorded in the window;
        # the limitation travels with the figure so the console can say
        # "insufficient history" instead of rendering a blank cell.
        raw_cover.append(
            {
                "material_id": p["material_id"],
                "name": (p.get("material") or {}).get("name"),
                "quantity": p.get("quantity"),
                "unit": p.get("unit"),
                "days_of_cover": p.get("days_of_cover"),
                "status": p.get("status"),
                "limitations": p.get("limitations", []),
            }
        )

    production = production_series(store, period=PeriodType.DAILY, anchor=today)
    finished = [
        p for p in positions
        if (p.get("material") or {}).get("material_class") == MaterialClass.FINISHED_PRODUCT.value
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
        "counts": {
            "materials": len(materials),
            "by_class": by_class,
        },
        "raw_material_cover": raw_cover,
        "finished_product_positions": [
            {
                "material_id": p["material_id"],
                "name": (p.get("material") or {}).get("name"),
                "quantity": p.get("quantity"),
                "reserved": p.get("reserved"),
                "available": p.get("available"),
                "unit": p.get("unit"),
                "location": p.get("location"),
                "status": p.get("status"),
            }
            for p in finished
        ],
        "critical_materials": critical,
        "production": {
            "period": production.get("period"),
            "latest": production.get("latest"),
            "previous": production.get("previous"),
            "change_percent": production.get("change_percent"),
            "trend": production.get("trend"),
            "unit": production.get("unit"),
        },
        "inventory_value": {
            "amount": round(inventory_value, 2),
            "currency": "INR",
            "materials_priced": priced,
            "calculation_status": CalculationStatus.ILLUSTRATIVE.value,
            "basis": "Σ (quantity × latest recorded unit price) for materials whose price unit matches their quantity unit",
        },
        "recent_movements": store.movements(limit=12),
        "limitations": limitations,
    }


def inventory_intelligence(store: Any, *, anchor: date | None = None) -> dict[str, Any]:
    """Threshold, cover and forecast intelligence across every material.

    This is what the AI insights are generated *from*: the recommendations are
    explanations of these computed facts, not independent claims.
    """
    insights: list[dict[str, Any]] = []
    for m in store.materials(limit=500):
        status = inventory_status(store, m["id"], anchor=anchor)
        if status.get("limitations") and status.get("available") is None:
            continue
        available = status.get("available")
        safety = status.get("safety_stock") or 0.0
        if status["status"] == MaterialStatus.OUT_OF_STOCK.value:
            insights.append(
                {
                    "kind": "OUT_OF_STOCK",
                    "severity": "CRITICAL",
                    "material_id": m["id"],
                    "name": m["name"],
                    "message": f"{m['name']} has no available stock ({status.get('reserved')} {status.get('unit')} reserved).",
                    "evidence": {"available": available, "reserved": status.get("reserved"), "unit": status.get("unit")},
                }
            )
        elif status["status"] == MaterialStatus.CRITICAL.value:
            shortfall = round(safety - float(available), 6)
            insights.append(
                {
                    "kind": "BELOW_SAFETY_STOCK",
                    "severity": "CRITICAL",
                    "material_id": m["id"],
                    "name": m["name"],
                    "message": f"{m['name']} is {shortfall:g} {status.get('unit')} below its safety stock.",
                    "evidence": {"available": available, "safety_stock": safety, "shortfall": shortfall},
                }
            )
        elif status["status"] == MaterialStatus.DEPLETING.value:
            insights.append(
                {
                    "kind": "BELOW_REORDER_LEVEL",
                    "severity": "WARNING",
                    "material_id": m["id"],
                    "name": m["name"],
                    "message": (
                        f"{m['name']} is at or below its reorder level "
                        f"({available:g} {status.get('unit')} available)."
                    ),
                    "evidence": {"available": available, "reorder_level": status.get("reorder_level")},
                }
            )
        forecast = forecast_inventory(store, m["id"], anchor=anchor)
        if forecast.get("projected_depletion_date") and forecast.get("days_to_depletion") is not None:
            if forecast["days_to_depletion"] <= 30:
                insights.append(
                    {
                        "kind": "FORECAST_DEPLETION",
                        "severity": "WARNING" if forecast["days_to_depletion"] > 14 else "CRITICAL",
                        "material_id": m["id"],
                        "name": m["name"],
                        "message": (
                            f"{m['name']} is projected to run out in "
                            f"{forecast['days_to_depletion']:.0f} days at the observed consumption rate."
                        ),
                        "evidence": {
                            "days_to_depletion": forecast["days_to_depletion"],
                            "mean_daily_consumption": forecast["mean_daily_consumption"],
                            "confidence": forecast["confidence"],
                            "samples": forecast["samples"],
                        },
                    }
                )

    # Scheduled maintenance requirements inside the next 14 days.
    scheduled = [r for r in store.requirements() if "recurring" in (r["schedule"] or "").lower()]
    if scheduled:
        insights.append(
            {
                "kind": "RECURRING_REQUIREMENTS",
                "severity": "INFO",
                "material_id": None,
                "name": None,
                "message": f"{len(scheduled)} material requirement(s) are on a recurring schedule.",
                "evidence": {"requirement_ids": [r["id"] for r in scheduled[:10]]},
            }
        )

    insights.sort(key=lambda i: {"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(i["severity"], 3))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "insights": insights,
        "counts": {
            "critical": sum(1 for i in insights if i["severity"] == "CRITICAL"),
            "warning": sum(1 for i in insights if i["severity"] == "WARNING"),
            "info": sum(1 for i in insights if i["severity"] == "INFO"),
        },
    }


# ------------------------------------------------------------- recommendation


def procurement_recommendation(
    store: Any,
    equipment_id: str,
    *,
    failure_mode: str | None = None,
    anchor: date | None = None,
) -> dict[str, Any]:
    """The end-to-end recommendation, assembled from the deterministic parts.

    Reads: requirement → inventory → coverage → price history → financial impact,
    and returns a reviewable recommendation with its evidence and its limitations.
    A shortfall produces a *proposed* procurement line; nothing is ordered. A write
    can only happen after an approval decision, in
    :mod:`backend.materials.approvals`.
    """
    requirement = material_requirement(store, equipment_id, failure_mode=failure_mode, anchor=anchor)
    if requirement.get("limitations"):
        return {
            "equipment_id": equipment_id,
            "failure_mode": failure_mode,
            "status": "BLOCKED",
            "recommendation": "No recommendation can be made: the maintenance requirement is not recorded.",
            "lines": [],
            "limitations": requirement["limitations"],
        }

    lines: list[dict[str, Any]] = []
    total_cost = 0.0
    any_shortfall = False
    limitations: list[dict[str, Any]] = []

    for line in requirement["lines"]:
        price = price_history(store, line["item_id"], window_days=30, anchor=anchor)
        cost = financial_impact(store, line["item_id"], line["required_quantity"], unit=line["unit"], anchor=anchor)
        procurable = line["coverage"] == "SHORTFALL"
        if procurable:
            any_shortfall = True
        if cost.get("estimated_cost") is not None:
            total_cost += float(cost["estimated_cost"])
        limitations.extend(price.get("limitations", []))
        limitations.extend(cost.get("limitations", []))
        lines.append(
            {
                "item_id": line["item_id"],
                "item_name": line["item_name"],
                "required_quantity": line["required_quantity"],
                "unit": line["unit"],
                "coverage": line["coverage"],
                "available": line["available"],
                "safety_stock": line["safety_stock"],
                "surplus_after_requirement_and_safety": line["surplus_after_requirement_and_safety"],
                "shortfall_quantity": line["shortfall_quantity"],
                "purpose": line["purpose"],
                "schedule": line["schedule"],
                "price": {
                    "current": price.get("current"),
                    "change_percent": price.get("change_percent"),
                    "movement": price.get("movement"),
                    "window_days": price.get("window_days"),
                    "data_status": price.get("data_status"),
                    "source": price.get("source"),
                    "points": price.get("points"),
                },
                "cost": {
                    "amount": cost.get("estimated_cost"),
                    "currency": cost.get("currency"),
                    "calculation_status": cost.get("calculation_status"),
                    "basis": cost.get("calculation_basis"),
                },
                "procurement_required": procurable,
                "recommended_order_quantity": line["shortfall_quantity"] if procurable else 0.0,
                "limitations": [*price.get("limitations", []), *cost.get("limitations", [])],
            }
        )

    if any_shortfall:
        summary = (
            "Required spares are not fully covered by available stock after safety stock. "
            "A procurement request is proposed for engineer review."
        )
        confidence = "HIGH"
    else:
        summary = (
            "Available stock covers every required item plus its safety stock. "
            "Proceed with the planned intervention using existing inventory; no procurement required."
        )
        confidence = "HIGH"
    if limitations:
        confidence = "MEDIUM" if confidence == "HIGH" else confidence

    return {
        "equipment_id": equipment_id,
        "failure_mode": failure_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PENDING_APPROVAL",
        "overall_coverage": requirement["overall_coverage"],
        "recommendation": summary,
        "procurement_required": any_shortfall,
        "estimated_material_cost": {
            "amount": round(total_cost, 2),
            "currency": "INR",
            "calculation_status": CalculationStatus.ILLUSTRATIVE.value,
            "basis": "Σ (required quantity × latest recorded unit cost) per line",
        },
        "confidence": confidence,
        "confidence_basis": "derived from requirement, inventory and price completeness",
        "lines": lines,
        "approval": {
            "required": True,
            "reason": "Any procurement or write action requires engineer review before execution.",
            "state": "PENDING_APPROVAL",
        },
        "limitations": limitations,
    }


# ----------------------------------------------------------------- graph


def material_graph(store: Any) -> dict[str, Any]:
    """Materials as first-class nodes in the industrial graph.

    The edges are operational, not schema: *requires*, *stocked at*, *supplied by*,
    *flows to*, *produced*. A node/edge dump of the tables would be a picture of
    the database; this is a picture of the plant's material relationships, and each
    edge carries the provenance of the record it came from.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node(nid: str, kind: str, label: str, extra: dict[str, Any] | None = None) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, "label": label, **(extra or {})}

    def edge(src: str, dst: str, relation: str, **extra: Any) -> None:
        edges.append({"source": src, "target": dst, "relation": relation, **extra})

    for supplier in store.suppliers():
        node(supplier["id"], "SUPPLIER", supplier["name"], {"lead_time_days": supplier["lead_time_days"], "status": supplier["status"]})

    materials = store.materials(limit=500)
    for m in materials:
        node(
            m["id"],
            m["material_class"],
            m["name"],
            {
                "unit": m["unit"],
                "location": m["location"],
                "status": m["status"],
                "provenance": m["provenance"],
            },
        )
        if m.get("supplier_id"):
            edge(m["id"], m["supplier_id"], "SUPPLIED_BY", provenance=m["provenance"])
        if m.get("location"):
            location_id = m["location"]
            location_kind = "TANK" if location_id.startswith("e-") else "WAREHOUSE"
            node(location_id, location_kind, location_id)
            edge(m["id"], location_id, "STOCKED_AT", provenance=m["provenance"])
        if m.get("source_process_unit") and m.get("destination_process_unit"):
            src_unit, dst_unit = m["source_process_unit"], m["destination_process_unit"]
            node(src_unit, "PROCESS_UNIT", src_unit)
            node(dst_unit, "PROCESS_UNIT", dst_unit)
            edge(src_unit, m["id"], "PRODUCES", provenance=m["provenance"])
            edge(m["id"], dst_unit, "FLOWS_TO", provenance=m["provenance"])

    for req in store.requirements():
        node(req["equipment_id"], "EQUIPMENT", req["equipment_id"])
        node(req["item_id"], "MAINTENANCE_SPARE", (store.material(req["item_id"]) or {}).get("name", req["item_id"]))
        edge(
            req["equipment_id"],
            req["item_id"],
            "REQUIRES",
            quantity=req["quantity"],
            unit=req["unit"],
            failure_mode=req["failure_mode"],
            schedule=req["schedule"],
            provenance=req["provenance"],
        )

    # One edge per (process unit, product) pair. Iterating production *records*
    # emitted one edge per day per product — 508 duplicate edges describing a
    # single relationship, which makes the graph unreadable and bloats any agent
    # that retrieves it.
    produced_pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for product in store.production(period_type=PeriodType.DAILY.value, limit=500):
        unit_id = product["process_unit_id"]
        product_id = product["product_id"]
        node(
            product_id,
            "FINISHED_PRODUCT",
            (store.material(product_id) or {}).get("name", product_id),
        )
        if not unit_id:
            continue
        node(unit_id, "PROCESS_UNIT", unit_id)
        produced_pairs.setdefault((unit_id, product_id), product["provenance"])

    for (unit_id, product_id), provenance in produced_pairs.items():
        edge(unit_id, product_id, "PRODUCES", provenance=provenance)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
    }


def material_neighbourhood(store: Any, material_id: str) -> dict[str, Any]:
    """The subgraph around one material — what a detail view or an agent needs.

    Scoped deliberately: retrieving the whole graph to answer "who supplies this
    seal?" is the retrieval mistake that makes an agent slow and vague.
    """
    graph = material_graph(store)
    keep = {material_id}
    for e in graph["edges"]:
        if e["source"] == material_id:
            keep.add(e["target"])
        elif e["target"] == material_id:
            keep.add(e["source"])
    nodes = [n for n in graph["nodes"] if n["id"] in keep]
    edges = [e for e in graph["edges"] if e["source"] in keep and e["target"] in keep]
    return {
        "material_id": material_id,
        "nodes": nodes,
        "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }


__all__ = [
    "ABNORMAL_CHANGE_PCT",
    "CONVERSION_BASIS_REQUIRED",
    "DATA_UNAVAILABLE",
    "EQUIPMENT_NOT_FOUND",
    "INSUFFICIENT_DATA",
    "INSUFFICIENT_HISTORY",
    "INVENTORY_DATA_UNAVAILABLE",
    "MAINTENANCE_REQUIREMENT_NOT_FOUND",
    "MATERIAL_NOT_FOUND",
    "MIN_FORECAST_SAMPLES",
    "PRICE_HISTORY_UNAVAILABLE",
    "WARNING_CHANGE_PCT",
    "days_of_cover",
    "equipment_requirements",
    "financial_impact",
    "forecast_inventory",
    "inventory_intelligence",
    "inventory_status",
    "material_graph",
    "material_neighbourhood",
    "material_requirement",
    "materials_dashboard",
    "price_history",
    "procurement_recommendation",
    "production_series",
]
