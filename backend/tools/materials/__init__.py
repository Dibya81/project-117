"""Agent-safe tools over the materials domain.

These are the AI's only route to inventory, price and production figures. Each one
calls :mod:`backend.materials.service`, which computes from stored rows, so the
model can read a number but cannot originate one. That is the whole point: a
language model that is asked "how much stock is there?" and has no tool will
answer anyway.

Three rules are enforced here rather than trusted to the prompt:

* **Read-only.** Every tool is ``RiskLevel.READ``. There is no tool that writes,
  orders or approves — procurement is proposed through
  ``generate_procurement_recommendation`` and executed only after a human
  approval, which is a separate flow.
* **Limitations are returned, not hidden.** When the service reports
  ``INSUFFICIENT_HISTORY`` or ``DATA_UNAVAILABLE`` the tool returns that code and
  message verbatim, so the model has something true to say instead of a gap to
  fill.
* **Scoped retrieval.** The tools take an id and return one material, one asset or
  one window. Nothing hands the model the whole inventory database or the whole
  graph.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.materials import service as svc
from backend.materials.models import PeriodType
from backend.storage.materials import MaterialsStore
from backend.tools.base import (
    Permission,
    ResourceLimits,
    RiskLevel,
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolUnavailable,
)


def _store(context: ToolContext) -> MaterialsStore:
    """The shared materials store, or a clear refusal.

    A missing store means the deployment has no materials layer wired up. Saying
    so is the honest answer; a tool that invented an empty inventory would let the
    agent report "no stock" about a plant it cannot see.
    """
    store = getattr(context, "materials", None)
    if store is None:
        raise ToolUnavailable(
            "the materials domain is not available in this deployment "
            "(no MaterialsStore on the tool context)"
        )
    return store


def _envelope(result: dict[str, Any], *, note: str = "") -> dict[str, Any]:
    """Wrap a service result with its provenance markers and any limitations."""
    payload = dict(result)
    if note:
        payload["tool_note"] = note
    limitations = payload.get("limitations") or []
    if limitations:
        payload["limitations"] = limitations
    return payload


# ------------------------------------------------------------------ arguments


class MaterialIdArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(description="Stable material id, e.g. RM-CRUDE-LIGHT or MECH-SEAL-P1001.")


class InventoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(description="Material id to read the current position for.")
    window_days: int = Field(default=30, ge=1, le=365, description="Consumption window used for days of cover.")


class MovementsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(description="Material id.")
    movement_type: str | None = Field(
        default=None,
        description="Optional filter: RECEIPT, TRANSFER, CONSUMPTION, PRODUCTION, DISPATCH or ADJUSTMENT.",
    )
    since: str | None = Field(default=None, description="ISO date lower bound (inclusive).")
    limit: int = Field(default=50, ge=1, le=200)


class ProductionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str = Field(default="DAILY", description="DAILY, WEEKLY or MONTHLY.")
    product_id: str | None = Field(default=None, description="Optional finished-product material id.")
    process_unit_id: str | None = Field(default=None, description="Optional plant asset id, e.g. e-COL-1044.")


class EquipmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    equipment_id: str = Field(description="Real plant asset id, e.g. e-P-1001 (pump P-1001).")
    failure_mode: str | None = Field(
        default=None,
        description="Optional diagnosed failure mode (seal_leak, bearing_wear, cavitation …) to prioritise the matching spare.",
    )


class MaintenanceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    equipment_id: str = Field(description="Real plant asset id.")
    failure_mode: str | None = Field(default=None, description="Optional diagnosed failure mode.")
    multiplier: float = Field(default=1.0, gt=0, le=100, description="Scale the requirement, e.g. 2 for two interventions.")


class PriceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(description="Material id whose price history to read.")
    window_days: int = Field(default=30, ge=1, le=730, description="7, 30, 90 or 365 are the usual windows.")


class ForecastArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(description="Material id to project depletion for.")


class RecommendationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    equipment_id: str = Field(description="Real plant asset id.")


# ---------------------------------------------------------------------- tools


class _BaseTool:
    """Shared plumbing: one spec shape, one delegation shape."""

    _spec: ToolSpec
    _arguments: type[BaseModel]

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    @property
    def arguments_model(self) -> type[BaseModel]:
        return self._arguments

    def _spec_for(
        self,
        *,
        name: str,
        description: str,
        arguments: type[BaseModel],
        capabilities: list[str],
        output_properties: dict[str, Any],
    ) -> ToolSpec:
        """Every materials tool shares these: read risk, read permission, capped output."""
        return ToolSpec(
            name=name,
            description=description,
            permission=Permission.DOCUMENTS_READ,
            risk=RiskLevel.READ,
            limits=ResourceLimits(timeout_seconds=30.0, max_output_bytes=128_000),
            capabilities=capabilities,
            latency_class=2,
            cost_class=1,
            input_schema=arguments.model_json_schema(),
            output_schema={"type": "object", "properties": output_properties},
        )


class GetMaterialTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = MaterialIdArgs
        self._spec = self._spec_for(
            name="get_material",
            description=(
                "Read one material's full record: class (RAW_MATERIAL, INTERMEDIATE, "
                "FINISHED_PRODUCT or MAINTENANCE_SPARE), unit, storage location, quality "
                "attributes and provenance. Use this first to learn a material's unit — "
                "never assume one, because spares are counted in EA while fluids are "
                "measured in MT, kg, KL or m3."
            ),
            arguments=MaterialIdArgs,
            capabilities=["materials", "read"],
            output_properties={
                "material": {"type": "object"},
                "inventory": {"type": "object"},
                "supplier": {"type": ["object", "null"]},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, MaterialIdArgs)
        store = _store(context)
        material = store.material(arguments.material_id)
        if material is None:
            return ToolResult(
                tool="get_material",
                status="not_found",
                output={"code": svc.MATERIAL_NOT_FOUND, "material_id": arguments.material_id},
                error=f"no material with id {arguments.material_id}",
            )
        supplier = store.supplier(material["supplier_id"]) if material.get("supplier_id") else None
        return ToolResult(
            tool="get_material",
            output=_envelope(
                {
                    "material": material,
                    "inventory": svc.inventory_status(store, arguments.material_id),
                    "supplier": supplier,
                    "data_status": material["provenance"].get("data_status"),
                }
            ),
        )


class GetInventoryStatusTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = InventoryArgs
        self._spec = self._spec_for(
            name="get_inventory_status",
            description=(
                "Current stock position for one material. Returns quantity, reserved, "
                "available (computed as quantity − reserved by the backend, never by you), "
                "safety stock, reorder level, unit, threshold status and days of cover. "
                "Quote 'available' — it is the figure that decides whether a requirement "
                "can be met. Days of cover is null with an INSUFFICIENT_HISTORY limitation "
                "when no consumption has been recorded; report that, do not estimate it."
            ),
            arguments=InventoryArgs,
            capabilities=["materials", "inventory", "read"],
            output_properties={
                "available": {"type": "number"},
                "reserved": {"type": "number"},
                "safety_stock": {"type": "number"},
                "unit": {"type": "string"},
                "status": {"type": "string"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, InventoryArgs)
        status = svc.inventory_status(
            _store(context), arguments.material_id, window_days=arguments.window_days
        )
        code = (status.get("limitations") or [{}])[0].get("code")
        if code == svc.MATERIAL_NOT_FOUND:
            return ToolResult(
                tool="get_inventory_status", status="not_found", output=status,
                error=f"no material with id {arguments.material_id}",
            )
        return ToolResult(tool="get_inventory_status", output=_envelope(status))


class GetMaterialMovementsTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = MovementsArgs
        self._spec = self._spec_for(
            name="get_material_movements",
            description=(
                "The append-only movement ledger for one material: RECEIPT, TRANSFER, "
                "CONSUMPTION, PRODUCTION, DISPATCH and ADJUSTMENT records, newest first, "
                "each with its source location, destination and reference document. Use it "
                "to explain where a quantity came from or went."
            ),
            arguments=MovementsArgs,
            capabilities=["materials", "history", "read"],
            output_properties={"items": {"type": "array"}, "count": {"type": "integer"}},
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, MovementsArgs)
        items = _store(context).movements(
            arguments.material_id,
            movement_type=arguments.movement_type,
            since=arguments.since,
            limit=arguments.limit,
        )
        return ToolResult(
            tool="get_material_movements",
            output={
                "items": items,
                "count": len(items),
                "material_id": arguments.material_id,
                "note": "Movements are append-only; corrections appear as ADJUSTMENT records.",
            },
        )


class GetProductionOutputTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = ProductionArgs
        self._spec = self._spec_for(
            name="get_production_output",
            description=(
                "Production output aggregated to DAILY, WEEKLY or MONTHLY, with the latest "
                "period, the previous complete period and the percentage change between them. "
                "The bucket containing today is flagged partial and is never used as a "
                "comparison baseline. Use this to answer 'how much did we produce' and "
                "'is it rising or falling' — never estimate either."
            ),
            arguments=ProductionArgs,
            capabilities=["production", "read"],
            output_properties={
                "buckets": {"type": "array"},
                "latest": {"type": "object"},
                "change_percent": {"type": ["number", "null"]},
                "trend": {"type": ["string", "null"]},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ProductionArgs)
        try:
            period = PeriodType(arguments.period.upper())
        except ValueError:
            return ToolResult(
                tool="get_production_output",
                status="invalid_arguments",
                output={"code": svc.INSUFFICIENT_DATA, "allowed": [p.value for p in PeriodType]},
                error=f"unknown period {arguments.period!r}",
            )
        result = svc.production_series(
            _store(context),
            period=period,
            product_id=arguments.product_id,
            process_unit_id=arguments.process_unit_id,
        )
        return ToolResult(tool="get_production_output", output=_envelope(result))


class GetEquipmentMaterialRequirementsTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = EquipmentArgs
        self._spec = self._spec_for(
            name="get_equipment_material_requirements",
            description=(
                "The materials an asset requires, resolved against live inventory. Pass the "
                "diagnosed failure_mode to rank the spare that answers that specific fault "
                "first. Returns required quantity, unit and the current available stock for "
                "each item. Equipment ids are real plant assets (e-P-1001 = pump P-1001); do "
                "not invent asset codes."
            ),
            arguments=EquipmentArgs,
            capabilities=["maintenance", "materials", "read"],
            output_properties={"requirements": {"type": "array"}},
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, EquipmentArgs)
        result = svc.equipment_requirements(
            _store(context), arguments.equipment_id, failure_mode=arguments.failure_mode
        )
        code = (result.get("limitations") or [{}])[0].get("code")
        if code == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND:
            return ToolResult(
                tool="get_equipment_material_requirements",
                status="not_found",
                output=result,
                error=f"no material requirement recorded for {arguments.equipment_id}",
            )
        return ToolResult(tool="get_equipment_material_requirements", output=_envelope(result))


class GetMaintenanceRequirementsTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = MaintenanceArgs
        self._spec = self._spec_for(
            name="get_maintenance_requirements",
            description=(
                "Required quantity against available stock and safety stock, per item, with "
                "the coverage verdict. The backend applies the rule "
                "'surplus = available − required − safety_stock; COVERED when surplus ≥ 0'. "
                "Report the surplus or shortfall it returns. Do not re-derive it yourself."
            ),
            arguments=MaintenanceArgs,
            capabilities=["maintenance", "inventory", "read"],
            output_properties={
                "overall_coverage": {"type": "string"},
                "lines": {"type": "array"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, MaintenanceArgs)
        result = svc.material_requirement(
            _store(context),
            arguments.equipment_id,
            failure_mode=arguments.failure_mode,
            multiplier=arguments.multiplier,
        )
        code = (result.get("limitations") or [{}])[0].get("code")
        if code == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND:
            return ToolResult(
                tool="get_maintenance_requirements",
                status="not_found",
                output=result,
                error=f"no material requirement recorded for {arguments.equipment_id}",
            )
        return ToolResult(tool="get_maintenance_requirements", output=_envelope(result))


class SearchPriceHistoryTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = PriceArgs
        self._spec = self._spec_for(
            name="search_price_history",
            description=(
                "Price observations for one item over a window: current price with its unit "
                "(INR/EA, INR/MT …), the baseline at the window start, the absolute and "
                "percentage change, and a NORMAL / WARNING / ABNORMAL movement flag. Also "
                "returns the data_status — SYNTHETIC_DEMO means a demonstration figure, not a "
                "market quote, and you must say so when you quote it."
            ),
            arguments=PriceArgs,
            capabilities=["pricing", "read"],
            output_properties={
                "current": {"type": "object"},
                "change_percent": {"type": "number"},
                "movement": {"type": "string"},
                "data_status": {"type": "string"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, PriceArgs)
        result = svc.price_history(_store(context), arguments.item_id, window_days=arguments.window_days)
        if result.get("status") == svc.PRICE_HISTORY_UNAVAILABLE:
            return ToolResult(
                tool="search_price_history",
                status="not_found",
                output=result,
                error=f"no price observations for {arguments.item_id}",
            )
        return ToolResult(tool="search_price_history", output=_envelope(result))


class CalculateMaterialRequirementTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = MaintenanceArgs
        self._spec = self._spec_for(
            name="calculate_material_requirement",
            description=(
                "Deterministic material requirement and cost for an asset's intervention. "
                "Returns the required quantity per item (scaled by 'multiplier' for repeat "
                "interventions), the total estimated cost with its arithmetic basis, and the "
                "coverage verdict. The backend performs every calculation here; quote its "
                "numbers and explain them, never compute your own."
            ),
            arguments=MaintenanceArgs,
            capabilities=["maintenance", "costing", "read"],
            output_properties={
                "lines": {"type": "array"},
                "overall_coverage": {"type": "string"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, MaintenanceArgs)
        store = _store(context)
        requirement = svc.material_requirement(
            store,
            arguments.equipment_id,
            failure_mode=arguments.failure_mode,
            multiplier=arguments.multiplier,
        )
        if requirement.get("limitations"):
            return ToolResult(
                tool="calculate_material_requirement",
                status="not_found",
                output=requirement,
                error=requirement["limitations"][0]["message"],
            )
        lines = []
        total = 0.0
        for line in requirement["lines"]:
            cost = svc.financial_impact(store, line["item_id"], line["required_quantity"], unit=line["unit"])
            if cost.get("estimated_cost") is not None:
                total += float(cost["estimated_cost"])
            lines.append({**line, "cost": cost})
        return ToolResult(
            tool="calculate_material_requirement",
            output={
                **requirement,
                "lines": lines,
                "estimated_total_cost": {
                    "amount": round(total, 2),
                    "currency": "INR",
                    "calculation_status": "ILLUSTRATIVE",
                    "basis": "Σ (required quantity × latest recorded unit cost)",
                },
            },
        )


class ForecastInventoryTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = ForecastArgs
        self._spec = self._spec_for(
            name="forecast_inventory",
            description=(
                "Project when a material runs out, from its recorded consumption. Returns a "
                "depletion date, the date it crosses safety stock, and a confidence grade with "
                "the sample count and dispersion it was derived from. It returns "
                "INSUFFICIENT_HISTORY and no date when fewer than three consumption days are "
                "recorded — in that case say a forecast is not possible, and never supply one."
            ),
            arguments=ForecastArgs,
            capabilities=["inventory", "forecasting", "read"],
            output_properties={
                "projected_depletion_date": {"type": ["string", "null"]},
                "confidence": {"type": "string"},
                "samples": {"type": "integer"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, ForecastArgs)
        result = svc.forecast_inventory(_store(context), arguments.material_id)
        return ToolResult(tool="forecast_inventory", output=_envelope(result))


class GenerateProcurementRecommendationTool(_BaseTool):
    def __init__(self) -> None:
        self._arguments = RecommendationArgs
        self._spec = self._spec_for(
            name="generate_procurement_recommendation",
            description=(
                "Compose the full maintenance-and-materials recommendation for an asset: "
                "requirement → inventory → coverage → price history → estimated cost → "
                "reviewable recommendation. Read-only: it orders nothing and writes nothing. "
                "It always returns status PENDING_APPROVAL, because any procurement needs an "
                "engineer's decision. Present it as a proposal awaiting approval, never as an "
                "action taken."
            ),
            arguments=RecommendationArgs,
            capabilities=["maintenance", "procurement", "recommendation", "read"],
            output_properties={
                "status": {"type": "string"},
                "recommendation": {"type": "string"},
                "procurement_required": {"type": "boolean"},
                "estimated_material_cost": {"type": "object"},
                "approval": {"type": "object"},
            },
        )

    async def run(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        assert isinstance(arguments, RecommendationArgs)
        result = svc.procurement_recommendation(_store(context), arguments.equipment_id)
        return ToolResult(
            tool="generate_procurement_recommendation",
            status="ok" if result.get("status") != "BLOCKED" else "not_found",
            output=_envelope(result),
            error=None if result.get("status") != "BLOCKED" else result.get("recommendation"),
        )


#: The materials capability set. Additive: registering these does not change what
#: the existing tools do, and every one is read-risk, so no approval gate is
#: newly tripped by their presence.
MATERIALS_TOOL_CLASSES = (
    GetMaterialTool,
    GetInventoryStatusTool,
    GetMaterialMovementsTool,
    GetProductionOutputTool,
    GetEquipmentMaterialRequirementsTool,
    GetMaintenanceRequirementsTool,
    SearchPriceHistoryTool,
    CalculateMaterialRequirementTool,
    ForecastInventoryTool,
    GenerateProcurementRecommendationTool,
)

MATERIALS_TOOL_NAMES = tuple(cls().spec.name for cls in MATERIALS_TOOL_CLASSES)

__all__ = [
    "MATERIALS_TOOL_CLASSES",
    "MATERIALS_TOOL_NAMES",
    "CalculateMaterialRequirementTool",
    "ForecastInventoryTool",
    "GenerateProcurementRecommendationTool",
    "GetEquipmentMaterialRequirementsTool",
    "GetInventoryStatusTool",
    "GetMaintenanceRequirementsTool",
    "GetMaterialMovementsTool",
    "GetMaterialTool",
    "GetProductionOutputTool",
    "SearchPriceHistoryTool",
]
