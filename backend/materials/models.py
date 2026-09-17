"""The industrial materials domain model.

Four material classes, because a refinery does not have "inventory rows": it has
feedstock that arrives by tanker, streams that exist only between two process
units, product sitting in a named tank, and spares on a shelf that exist to keep a
specific machine running. Collapsing those into one generic item table loses the
relationships that make the layer useful, so each is a distinct class with its own
required fields.

Every persisted entity carries :class:`Provenance`. A quantity without a source
and a timestamp is not data, it is a rumour, and this layer is meant to be
defensible in front of an engineer.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.materials.units import Unit, parse_unit


def now_iso() -> str:
    """A UTC ISO-8601 timestamp. One helper, so every record agrees on format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    """A stable, prefixed identifier. Prefixed so an id names its own type."""
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


class MaterialClass(str, Enum):
    """The four classes. The class decides which fields are meaningful."""

    RAW_MATERIAL = "RAW_MATERIAL"
    INTERMEDIATE = "INTERMEDIATE"
    FINISHED_PRODUCT = "FINISHED_PRODUCT"
    MAINTENANCE_SPARE = "MAINTENANCE_SPARE"


MATERIAL_CLASS_LABEL: dict[MaterialClass, str] = {
    MaterialClass.RAW_MATERIAL: "Raw material / feedstock",
    MaterialClass.INTERMEDIATE: "Intermediate / process stream",
    MaterialClass.FINISHED_PRODUCT: "Finished product",
    MaterialClass.MAINTENANCE_SPARE: "Maintenance spare / consumable",
}


class MaterialStatus(str, Enum):
    """Operational state of a material position."""

    NORMAL = "NORMAL"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DEPLETING = "DEPLETING"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class DataStatus(str, Enum):
    """Where a value came from. Never hidden, never defaulted to ACTUAL.

    ``SYNTHETIC_DEMO`` is a first-class status rather than something buried in a
    note: this deployment ships coherent demo data, and a figure that came from it
    must be distinguishable from a reading an instrument produced.
    """

    ACTUAL = "ACTUAL"
    IMPORTED = "IMPORTED"
    MANUAL = "MANUAL"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"


class CalculationStatus(str, Enum):
    """How a derived number should be read."""

    COMPUTED = "COMPUTED"
    ESTIMATED = "ESTIMATED"
    ILLUSTRATIVE = "ILLUSTRATIVE"
    VERIFIED = "VERIFIED"


class MovementType(str, Enum):
    RECEIPT = "RECEIPT"
    TRANSFER = "TRANSFER"
    CONSUMPTION = "CONSUMPTION"
    PRODUCTION = "PRODUCTION"
    DISPATCH = "DISPATCH"
    ADJUSTMENT = "ADJUSTMENT"


class PeriodType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class SupplierStatus(str, Enum):
    ACTIVE = "ACTIVE"
    QUALIFIED = "QUALIFIED"
    SUSPENDED = "SUSPENDED"
    ON_HOLD = "ON_HOLD"


class FinancialEventType(str, Enum):
    MATERIAL_COST = "MATERIAL_COST"
    ENERGY_COST = "ENERGY_COST"
    MAINTENANCE_COST = "MAINTENANCE_COST"
    INVENTORY_COST = "INVENTORY_COST"
    PRODUCTION_VALUE = "PRODUCTION_VALUE"


class Provenance(BaseModel):
    """Source, when, and how much to trust it.

    Attached to every entity and to most computed responses. ``source`` names the
    system of record (a store, a dataset, an operator); ``data_status`` says what
    kind of thing it is; ``note`` carries anything that does not fit.
    """

    source: str
    timestamp: str = Field(default_factory=now_iso)
    data_status: DataStatus = DataStatus.SYNTHETIC_DEMO
    note: str = ""

    @classmethod
    def synthetic(cls, source: str, note: str = "") -> "Provenance":
        return cls(source=source, data_status=DataStatus.SYNTHETIC_DEMO, note=note)

    @classmethod
    def computed(cls, source: str, note: str = "") -> "Provenance":
        """For backend-derived values: still synthetic input, but clearly derived."""
        return cls(source=source, data_status=DataStatus.SYNTHETIC_DEMO, note=note)


class Material(BaseModel):
    id: str
    name: str
    material_class: MaterialClass
    unit: Unit
    location: str = ""
    status: MaterialStatus = MaterialStatus.NORMAL
    description: str = ""
    #: Free-form quality properties (grade, sulphur %, API gravity …). Kept as a
    #: dict because quality attributes are genuinely material-specific.
    quality_attributes: dict[str, Any] = Field(default_factory=dict)
    supplier_id: str | None = None
    #: What the cost basis refers to — e.g. "landed cost, ex-tax".
    cost_basis: str = ""
    #: For INTERMEDIATE materials: the units the stream runs between.
    source_process_unit: str | None = None
    destination_process_unit: str | None = None
    provenance: Provenance
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)

    @property
    def class_label(self) -> str:
        return MATERIAL_CLASS_LABEL[self.material_class]


class InventoryBalance(BaseModel):
    """A material position at one location, at one time.

    ``available_quantity`` is deliberately NOT a stored column and NOT computable
    by a model: it is ``quantity - reserved``, evaluated here, once.
    """

    id: str
    material_id: str
    location: str
    quantity: float
    reserved: float = 0.0
    unit: Unit
    threshold: float | None = None
    safety_stock: float = 0.0
    reorder_level: float = 0.0
    timestamp: str = Field(default_factory=now_iso)
    provenance: Provenance

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)

    @property
    def available_quantity(self) -> float:
        """Deterministic: quantity − reserved. The only definition in the system."""
        return round(self.quantity - self.reserved, 6)

    # The threshold → status rule lives in `backend.materials.service.inventory_status`
    # and nowhere else. It was briefly duplicated here as a property, which is
    # exactly how two parts of a system come to disagree about whether a material
    # is critical.


class MaterialMovement(BaseModel):
    """An immutable record of something that happened to a material.

    Movements are append-only. A correction is a new ADJUSTMENT movement, never
    an edit — an inventory history that can be rewritten cannot be audited.
    """

    id: str
    material_id: str
    movement_type: MovementType
    quantity: float
    unit: Unit
    timestamp: str
    source_location: str = ""
    destination_location: str = ""
    reference: str = ""
    provenance: Provenance

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)


class ProductionOutput(BaseModel):
    id: str
    product_id: str
    process_unit_id: str
    quantity: float
    unit: Unit
    period_type: PeriodType
    period_start: str
    period_end: str
    source: str = ""
    provenance: Provenance
    #: Opening + receipts − dispatches ± adjustments = closing. Stored per record
    #: so a period can be reconciled without re-deriving it from the whole log.
    opening: float | None = None
    receipts: float | None = None
    dispatches: float | None = None
    adjustments: float | None = None
    closing: float | None = None

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)

    def reconciled(self) -> float | None:
        """closing computed from the roll-forward, or None if inputs are missing."""
        if None in (self.opening, self.receipts, self.dispatches):
            return None
        return round(
            (self.opening or 0) + (self.receipts or 0) - (self.dispatches or 0) + (self.adjustments or 0),
            6,
        )


class PriceObservation(BaseModel):
    """One price, at one time, from one source. Append-only.

    ``unit`` is mandatory. ₹/kg and ₹/MT differ by 1000×, so a price row without
    its basis unit is worse than no row at all.
    """

    id: str
    item_id: str
    price: float
    currency: str = "INR"
    unit: Unit
    observed_on: str
    source: str
    data_status: DataStatus = DataStatus.SYNTHETIC_DEMO
    provenance: Provenance
    note: str = ""

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)

    @property
    def price_unit(self) -> str:
        return f"{self.currency}/{self.unit.value}"


class EquipmentMaterialRequirement(BaseModel):
    """The bridge between an asset and the material it consumes.

    ``equipment_id`` is a real Project 117 plant asset id (``e-P-1001``), never a
    fabricated asset code — the join has to land on the live plant or the whole
    recommendation chain is fiction.
    """

    id: str
    equipment_id: str
    item_id: str
    quantity: float
    unit: Unit
    schedule: str = ""
    purpose: str = ""
    #: Which failure mode this requirement answers, when it is mode-specific.
    failure_mode: str | None = None
    provenance: Provenance

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Unit:
        return parse_unit(v)


class Supplier(BaseModel):
    id: str
    name: str
    lead_time_days: int
    status: SupplierStatus = SupplierStatus.ACTIVE
    contact: str = ""
    reference: str = ""
    provenance: Provenance


class FinancialEvent(BaseModel):
    id: str
    event_type: FinancialEventType
    amount: float
    currency: str = "INR"
    occurred_on: str
    reference: str = ""
    calculation_status: CalculationStatus = CalculationStatus.ESTIMATED
    basis: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


def period_bounds(period_type: PeriodType, anchor: date) -> tuple[str, str]:
    """Inclusive start/end dates for the period containing ``anchor``.

    One definition of "this week" for the whole system — two callers disagreeing
    about whether a week starts on Sunday is how period-over-period comparisons
    quietly stop meaning anything.
    """
    if period_type is PeriodType.DAILY:
        return anchor.isoformat(), anchor.isoformat()
    if period_type is PeriodType.WEEKLY:
        start = date.fromordinal(anchor.toordinal() - anchor.weekday())  # Monday
        end = date.fromordinal(start.toordinal() + 6)
        return start.isoformat(), end.isoformat()
    start = anchor.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day)
    return start.isoformat(), end.isoformat()


__all__ = [
    "CalculationStatus",
    "DataStatus",
    "EquipmentMaterialRequirement",
    "FinancialEvent",
    "FinancialEventType",
    "InventoryBalance",
    "MATERIAL_CLASS_LABEL",
    "Material",
    "MaterialClass",
    "MaterialMovement",
    "MaterialStatus",
    "MovementType",
    "PeriodType",
    "PriceObservation",
    "ProductionOutput",
    "Provenance",
    "Supplier",
    "SupplierStatus",
    "new_id",
    "now_iso",
    "period_bounds",
]
