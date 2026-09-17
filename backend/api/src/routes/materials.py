"""Materials, inventory and business-intelligence endpoints.

Every response is computed by :mod:`backend.materials.service` from stored rows.
Nothing here calculates: the route layer validates input, calls the service and
returns its result, so the web console, the Android client and the agent tools all
receive the same numbers from the same code.

Pagination, filtering and date ranges are supported on every collection, because
the alternative — returning the whole materials database — is what makes the
frontend slow and an agent's context useless. Agent-facing retrieval is scoped by
:func:`material_neighbourhood`, which returns one material's subgraph rather than
the whole graph.

Route order matters: the parameterised ``/materials/{material_id}`` is declared
last so it cannot shadow ``/materials/inventory`` or ``/materials/graph``.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.src.deps import get_audit, get_materials, get_operations, get_principal
from backend.materials import service as svc
from backend.materials.models import DataStatus, MovementType, PeriodType
from backend.materials.seed import seed_materials
from backend.security.audit import AuditService
from backend.security.rbac import Principal
from backend.storage.materials import MaterialsStore
from backend.storage.operations import OperationsDataUnavailable, OperationsStore

router = APIRouter(prefix="/api/materials", tags=["materials"])

#: Reported on collection responses so a client can display the basis without
#: inspecting each row.
DATASET_SOURCE = "PROJECT117-SYNTHETIC-DEMO"


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, 200)), max(0, offset)


# ------------------------------------------------------------------ inventory


@router.get("/inventory")
def inventory(
    material_class: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Positions for every material, with coverage where it can be computed."""
    limit, offset = _page(limit, offset)
    materials = store.materials(material_class=material_class, search=search, limit=limit, offset=offset)
    rows = [svc.inventory_status(store, m["id"]) for m in materials]
    return {
        "items": rows,
        "count": len(rows),
        "total": store.count_materials(material_class=material_class, search=search),
        "limit": limit,
        "offset": offset,
        "source": DATASET_SOURCE,
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
        "calculation_basis": {"available": "quantity − reserved"},
    }


@router.get("/inventory/{material_id}")
def inventory_one(
    material_id: str,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    status = svc.inventory_status(store, material_id)
    if status.get("limitations") and status["limitations"][0]["code"] == svc.MATERIAL_NOT_FOUND:
        raise HTTPException(status_code=404, detail={"code": svc.MATERIAL_NOT_FOUND, "message": f"unknown material {material_id}"})
    return status


# ------------------------------------------------------------------ movements


@router.get("/movements")
def movements(
    material_id: str | None = None,
    movement_type: MovementType | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    limit, offset = _page(limit, offset)
    rows = store.movements(
        material_id,
        movement_type=movement_type.value if movement_type else None,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return {
        "items": rows,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "note": "Movements are append-only; a correction is a new ADJUSTMENT record.",
        "source": DATASET_SOURCE,
    }


# ----------------------------------------------------------------- production


@router.get("/production")
def production(
    period: PeriodType = PeriodType.DAILY,
    product_id: str | None = None,
    process_unit_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """DAILY, WEEKLY and MONTHLY output, aggregated from the stored daily records."""
    return svc.production_series(
        store,
        period=period,
        product_id=product_id,
        process_unit_id=process_unit_id,
        since=since,
        until=until,
    )


# --------------------------------------------------------------- price history


@router.get("/price-history/{item_id}")
def price_history(
    item_id: str,
    window_days: int = Query(30, ge=1, le=730, description="7, 30, 90 or 365 typical"),
    unit: str | None = Query(None, description="Re-base the series onto this unit"),
    abnormal_pct: float | None = Query(None, ge=0, description="Configurable abnormality threshold"),
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    kwargs = {"window_days": window_days, "target_unit": unit}
    if abnormal_pct is not None:
        kwargs["abnormal_pct"] = abnormal_pct
    result = svc.price_history(store, item_id, **kwargs)
    if result.get("status") == svc.PRICE_HISTORY_UNAVAILABLE:
        raise HTTPException(
            status_code=404,
            detail={"code": svc.PRICE_HISTORY_UNAVAILABLE, "message": f"no price history for {item_id}"},
        )
    return result


# ------------------------------------------------------- equipment / spares


@router.get("/equipment-requirements")
def equipment_requirements(
    equipment_id: str | None = None,
    item_id: str | None = None,
    failure_mode: str | None = None,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """The equipment→material bridge, optionally resolved against live inventory."""
    if equipment_id:
        return svc.equipment_requirements(store, equipment_id, failure_mode=failure_mode)
    rows = store.requirements(item_id=item_id, failure_mode=failure_mode)
    return {"items": rows, "count": len(rows), "source": DATASET_SOURCE}


@router.get("/maintenance-requirements/{equipment_id}")
def maintenance_requirements(
    equipment_id: str,
    failure_mode: str | None = None,
    multiplier: float = Query(1.0, gt=0, le=100),
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Required quantity vs available stock vs safety stock, with the coverage rule."""
    result = svc.material_requirement(store, equipment_id, failure_mode=failure_mode, multiplier=multiplier)
    if result.get("limitations") and result["limitations"][0]["code"] == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND:
        raise HTTPException(
            status_code=404,
            detail={"code": svc.MAINTENANCE_REQUIREMENT_NOT_FOUND, "message": f"no requirement for {equipment_id}"},
        )
    return result


@router.post("/procurement-recommendations")
def procurement_recommendations(
    equipment_id: str,
    failure_mode: str | None = None,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Compose a recommendation for engineer review.

    POST because it composes a proposal, but it is **read-only**: no order is
    placed and no row is written. Execution requires an approval decision.
    """
    return svc.procurement_recommendation(store, equipment_id, failure_mode=failure_mode)


@router.post("/procurement-requests")
def raise_procurement_request(
    equipment_id: str,
    failure_mode: str | None = None,
    store: MaterialsStore = Depends(get_materials),
    operations: OperationsStore = Depends(get_operations),
    audit: AuditService = Depends(get_audit),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Compose the recommendation and park it in the EXISTING approval queue.

    This is the boundary the whole layer is built around. The endpoint:

    * recomputes the recommendation server-side, so what a reviewer sees is the
      domain's own output and not something the browser assembled;
    * raises a **pending** approval only — it orders nothing, reserves nothing and
      changes no inventory;
    * is idempotent per equipment, so re-raising returns the open approval;
    * is audited with the acting principal.

    Execution after approval remains a separate, deliberately unbuilt step. A
    system that can buy a spare because a model suggested it is not a system an
    engineer should trust.
    """
    recommendation = svc.procurement_recommendation(store, equipment_id, failure_mode=failure_mode)
    if recommendation.get("status") == "BLOCKED":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_RECOMMENDATION",
                "message": recommendation.get("recommendation", "no recommendation could be composed"),
            },
        )

    lines = recommendation.get("lines", [])
    short = [ln for ln in lines if ln.get("procurement_required")]
    cost = recommendation.get("estimated_material_cost", {})
    summary = (
        f"{recommendation.get('recommendation', '')} "
        f"Estimated material cost {cost.get('amount')} {cost.get('currency', 'INR')} "
        f"({cost.get('calculation_status', 'ILLUSTRATIVE')})."
    ).strip()

    try:
        approval = operations.request_approval(
            title=(
                f"Procurement review — {equipment_id}"
                + (f" / {failure_mode}" if failure_mode else "")
            ),
            approval_type="procurement",
            actor=principal.user,
            summary=summary,
            related_id=f"procurement:{equipment_id}",
            risk="medium",
            required_role="engineer",
            evidence=[
                {
                    "kind": "recommendation",
                    "equipment_id": equipment_id,
                    "failure_mode": failure_mode,
                    "overall_coverage": recommendation.get("overall_coverage"),
                    "procurement_required": recommendation.get("procurement_required"),
                    "confidence": recommendation.get("confidence"),
                    "lines": [
                        {
                            "item_id": ln["item_id"],
                            "required_quantity": ln["required_quantity"],
                            "unit": ln["unit"],
                            "available": ln["available"],
                            "safety_stock": ln["safety_stock"],
                            "coverage": ln["coverage"],
                            "recommended_order_quantity": ln["recommended_order_quantity"],
                            "unit_price": (ln.get("price") or {}).get("current"),
                            "cost": (ln.get("cost") or {}).get("amount"),
                        }
                        for ln in lines
                    ],
                    "shortfall_lines": [ln["item_id"] for ln in short],
                    "limitations": recommendation.get("limitations", []),
                    "data_status": DataStatus.SYNTHETIC_DEMO.value,
                }
            ],
        )
    except OperationsDataUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "operations_unavailable", "message": str(exc)},
        ) from exc

    audit.record(
        action="materials.procurement_requested",
        resource_type="equipment",
        resource_id=equipment_id,
        user=principal.user,
        approval="pending",
        detail={
            "approval_id": approval["id"],
            "failure_mode": failure_mode,
            "procurement_required": recommendation.get("procurement_required"),
            "estimated_cost": cost.get("amount"),
            "deduplicated": approval.get("deduplicated", False),
        },
    )

    return {
        "recommendation": recommendation,
        "approval": approval,
        "note": (
            "No order has been placed. This is a request for engineer review; "
            "deciding it happens in the Approvals surface."
        ),
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
    }


# ------------------------------------------------------------------ suppliers


@router.get("/suppliers")
def suppliers(
    status: str | None = None,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    rows = store.suppliers(status=status)
    return {
        "items": rows,
        "count": len(rows),
        "note": "Synthetic demonstration suppliers; not real vendors.",
        "source": DATASET_SOURCE,
    }


# ------------------------------------------------------------------- finance


@router.get("/financial-events")
def financial_events(
    event_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    limit, _ = _page(limit, 0)
    rows = store.financial_events(event_type=event_type, since=since, until=until, limit=limit)
    return {
        "items": rows,
        "count": len(rows),
        "note": "Material and production values are illustrative synthetic figures.",
        "source": DATASET_SOURCE,
    }


# --------------------------------------------------------------- intelligence


@router.get("/intelligence")
def intelligence(
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Dashboard summary + threshold/forecast insights. Evidence-backed throughout."""
    anchor = date.today()
    return {
        "dashboard": svc.materials_dashboard(store, anchor=anchor),
        "intelligence": svc.inventory_intelligence(store, anchor=anchor),
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
    }


@router.get("/graph")
def graph(
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """The industrial relationship graph: requires / stocked at / supplied by / flows to."""
    return svc.material_graph(store)


@router.get("/graph/{material_id}")
def graph_neighbourhood(
    material_id: str,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """One material's subgraph — the scoped retrieval an agent should use."""
    if store.material(material_id) is None:
        raise HTTPException(status_code=404, detail={"code": svc.MATERIAL_NOT_FOUND, "message": f"unknown material {material_id}"})
    return svc.material_neighbourhood(store, material_id)


# ------------------------------------------------------------------- seeding


@router.post("/seed")
def seed(
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Populate coherent synthetic demo data. Refuses a non-empty store."""
    if not store.is_empty():
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_SEEDED", "message": "the materials store already contains data"},
        )
    return seed_materials(store)


# ------------------------------------------------------------------- material
# Declared LAST: a parameterised path at this position would otherwise swallow
# /inventory, /graph, /suppliers and every other literal route above.


@router.get("/{material_id}")
def material_detail(
    material_id: str,
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """Everything the detail view and an agent need for one material.

    Composed from the same service calls the individual endpoints use, so the
    aggregate can never disagree with the parts.
    """
    material = store.material(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail={"code": svc.MATERIAL_NOT_FOUND, "message": f"unknown material {material_id}"})

    status = svc.inventory_status(store, material_id)
    supplier = store.supplier(material["supplier_id"]) if material.get("supplier_id") else None
    requirement_rows = store.requirements(item_id=material_id)
    equipment_ids = sorted({r["equipment_id"] for r in requirement_rows})

    return {
        "material": material,
        "class_label": material["material_class"],
        "inventory": status,
        "movements": store.movements(material_id, limit=50),
        "price_history": svc.price_history(store, material_id, window_days=30),
        "forecast": svc.forecast_inventory(store, material_id),
        "supplier": supplier,
        "required_by": [
            {
                "equipment_id": r["equipment_id"],
                "requirement_id": r["id"],
                "quantity": r["quantity"],
                "unit": r["unit"],
                "schedule": r["schedule"],
                "purpose": r["purpose"],
                "failure_mode": r["failure_mode"],
            }
            for r in requirement_rows
        ],
        "upcoming_requirements": _upcoming(store, equipment_ids, material_id),
        "graph": svc.material_neighbourhood(store, material_id),
        "provenance": material["provenance"],
        "data_status": material["provenance"].get("data_status", ""),
    }


def _upcoming(store: MaterialsStore, equipment_ids: list[str], item_id: str) -> list[dict]:
    """Requirements on the assets that use this material, with the coverage gap.

    Returned per *equipment*, because "is there enough for the next intervention?"
    is a question about a job, not about a shelf.
    """
    out: list[dict] = []
    for equipment_id in equipment_ids:
        resolved = svc.material_requirement(store, equipment_id)
        for line in resolved.get("lines", []):
            if line["item_id"] != item_id:
                continue
            out.append(
                {
                    "equipment_id": equipment_id,
                    "schedule": line.get("schedule"),
                    "purpose": line.get("purpose"),
                    "required_quantity": line["required_quantity"],
                    "available": line["available"],
                    "safety_stock": line["safety_stock"],
                    "coverage": line["coverage"],
                    "gap": line["shortfall_quantity"],
                    "unit": line["unit"],
                }
            )
    return out


# ------------------------------------------------------------------ catalogue


@router.get("")
def list_materials(
    material_class: str | None = None,
    search: str | None = None,
    supplier_id: str | None = None,
    location: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "name",
    store: MaterialsStore = Depends(get_materials),
    principal: Principal = Depends(get_principal),
) -> dict:
    """The material catalogue: paginated, filterable, never the whole table."""
    limit, offset = _page(limit, offset)
    rows = store.materials(
        material_class=material_class,
        supplier_id=supplier_id,
        location=location,
        search=search,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )
    return {
        "items": rows,
        "count": len(rows),
        "total": store.count_materials(material_class=material_class, search=search),
        "limit": limit,
        "offset": offset,
        "source": DATASET_SOURCE,
        "data_status": DataStatus.SYNTHETIC_DEMO.value,
    }
