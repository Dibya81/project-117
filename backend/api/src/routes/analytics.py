"""Analytics endpoints (insights surface).

Every number returned here is either

* **computed** from the committed dataset in ``data/demo`` (equipment counts,
  open work orders, pending approvals) — see ``DemoStore.analytics``, or
* **measured** by the running process (request counts, latencies, tool and
  model call counters) — from the in-process ``MetricsRegistry``.

Nothing is a decorative constant. If the dataset is missing the endpoint
answers ``503`` rather than rendering a plausible-looking chart.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.src.deps import get_metrics, get_operations, get_principal
from backend.api.src.routes.equipment import authorize, unavailable
from backend.observability.metrics import MetricsRegistry
from backend.security.rbac import Principal
from backend.storage.demo import SOURCE, DemoDataUnavailable, DemoStore
from backend.tools.base import Permission

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

SERIES = (
    "vibrationC3",
    "workOrdersOpened",
    "workOrdersClosed",
    "aiTasksCompleted",
    "verificationPassRate",
    "mttrDays",
)


@router.get("/summary")
def analytics_summary(
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
    metrics: MetricsRegistry = Depends(get_metrics),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    try:
        computed = operations.analytics()
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "equipment": computed["equipment"],
        "workOrders": computed["workOrders"],
        "approvals": computed["approvals"],
        "platform": metrics.snapshot(),
        "computedAt": computed["computedAt"],
        "sources": {
            "operations": SOURCE,
            "platform": "in_process_metrics",
        },
    }


@router.get("/trends")
def analytics_trends(
    series: list[str] | None = Query(default=None, description=f"subset of {list(SERIES)}"),
    principal: Principal = Depends(get_principal),
    operations: DemoStore = Depends(get_operations),
) -> dict:
    authorize(principal, Permission.CONNECTORS_READ)
    requested = series or list(SERIES)
    unknown = [name for name in requested if name not in SERIES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown series {unknown}; expected a subset of {list(SERIES)}",
        )
    try:
        trends = operations.analytics()["trends"]
    except DemoDataUnavailable as exc:
        raise unavailable(exc) from exc
    return {
        "series": {name: trends.get(name, []) for name in requested},
        "available": list(SERIES),
        "source": SOURCE,
    }
