"""Deterministic industrial unit system.

This module is the **only** authority on unit conversion in Project 117. No
frontend, no Android client and no language model converts anything: they ask the
backend and receive a value plus the basis it was computed on.

The rules it enforces, and why each one exists:

1. **The original unit is never lost.** :class:`Quantity` keeps `unit` and the
   :class:`ConversionBasis` it was converted with, so a stored record can always
   be explained back to the reading it came from.

2. **Only same-dimension conversions are silent.** kg → MT is arithmetic and
   needs no outside information. KL → MT is *not*: it depends on the density of
   the specific material, which varies by grade, temperature and source. A
   universal density does not exist, so this module refuses to guess one and
   raises :class:`ConversionBasisRequired` instead. That refusal is the feature.

3. **The basis that was used is returned.** `Conversion.basis_used` and
   `Conversion.note` travel with the result so callers can persist them.
   A converted figure with no recorded basis is unauditable.

4. **Ambiguity is rejected, not resolved.** An unknown unit string is an error.
   A non-positive or non-finite density is an error. Silently treating either as
   1.0 would corrupt every downstream inventory and financial figure.

`MT` and `tonne` are both first-class because industrial documents use both; they
are the same mass (1000 kg) and therefore interchangeable, which is a fact, not an
assumption. `KL` and `m³` are likewise the same volume (1 kL ≡ 1 m³ by SI
definition), so no density is involved in that pair.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UnitError(ValueError):
    """Base class for every refusal in this module."""


class UnsupportedUnit(UnitError):
    """The unit string is not one this system knows."""


class ConversionBasisRequired(UnitError):
    """A cross-dimension conversion was attempted without a density basis.

    Raised for e.g. ``KL → MT``. The message names both units and says what
    would be needed, because "conversion failed" is not actionable.
    """


class InvalidBasis(UnitError):
    """A basis was supplied but cannot be used (non-finite, zero or negative)."""


class IncompatibleUnits(UnitError):
    """Two values were compared or combined without a common basis."""


class Unit(str, Enum):
    """The first-class units. Anything else is rejected at the boundary.

    Fluid quantities are measured in the mass and volume units listed here.
    ``EA`` (each) exists because a mechanical seal, a bearing and a filter
    cartridge are *counted*, not weighed: forcing them into kilograms would mean
    inventing a mass for every part, and the numbers would be fiction. ``EA`` is a
    separate dimension that never converts to mass or volume — see
    :func:`convert`, which refuses that bridge rather than approximating it.
    """

    KG = "kg"
    TONNE = "tonne"
    MT = "MT"
    KL = "KL"
    M3 = "m3"
    EA = "EA"


MASS_UNITS: frozenset[Unit] = frozenset({Unit.KG, Unit.TONNE, Unit.MT})
VOLUME_UNITS: frozenset[Unit] = frozenset({Unit.KL, Unit.M3})
COUNT_UNITS: frozenset[Unit] = frozenset({Unit.EA})

#: Display labels — the symbols an operator reads.
UNIT_LABEL: dict[Unit, str] = {
    Unit.KG: "kg",
    Unit.TONNE: "tonne",
    Unit.MT: "MT",
    Unit.KL: "KL",
    Unit.M3: "m³",
    Unit.EA: "ea",
}

#: Factor to the dimension's base unit. Mass base kg, volume base m³.
#: 1 tonne = 1 MT = 1000 kg (metric ton, SI-accepted).
#: 1 KL = 1 m³ (exact, by SI definition of the litre).
_TO_BASE: dict[Unit, float] = {
    Unit.KG: 1.0,
    Unit.TONNE: 1000.0,
    Unit.MT: 1000.0,
    Unit.KL: 1.0,
    Unit.M3: 1.0,
    Unit.EA: 1.0,
}

#: What a unit's price is quoted per, e.g. ₹/MT.
PRICE_UNITS: tuple[str, ...] = (
    "INR/kg",
    "INR/tonne",
    "INR/MT",
    "INR/KL",
    "INR/m3",
    "INR/EA",
)


def parse_unit(value: str | Unit) -> Unit:
    """Coerce a string to a :class:`Unit`, refusing anything unknown.

    Accepts the common spellings a document might use for the same unit, but only
    where the equivalence is exact — ``m3``/``m³``/``cubic metre`` are the same
    volume; there is no spelling of "tonne" that means something else.
    """
    if isinstance(value, Unit):
        return value
    raw = (value or "").strip()
    aliases = {
        "kg": Unit.KG,
        "kgs": Unit.KG,
        "kilogram": Unit.KG,
        "kilograms": Unit.KG,
        "t": Unit.TONNE,
        "tonne": Unit.TONNE,
        "tonnes": Unit.TONNE,
        "ton": Unit.TONNE,
        "tons": Unit.TONNE,
        "mt": Unit.MT,
        "metric ton": Unit.MT,
        "metric tons": Unit.MT,
        "metric tonne": Unit.MT,
        "kl": Unit.KL,
        "kilolitre": Unit.KL,
        "kiloliter": Unit.KL,
        "m3": Unit.M3,
        "m³": Unit.M3,
        "cum": Unit.M3,
        "cubic metre": Unit.M3,
        "cubic meter": Unit.M3,
        "ea": Unit.EA,
        "each": Unit.EA,
        "no": Unit.EA,
        "nos": Unit.EA,
        "unit": Unit.EA,
        "units": Unit.EA,
        "piece": Unit.EA,
        "pieces": Unit.EA,
        "pcs": Unit.EA,
    }
    hit = aliases.get(raw.lower())
    if hit is None:
        raise UnsupportedUnit(
            f"unknown unit {value!r}; supported: {', '.join(u.value for u in Unit)}"
        )
    return hit


def is_mass(unit: Unit | str) -> bool:
    return parse_unit(unit) in MASS_UNITS


def is_volume(unit: Unit | str) -> bool:
    return parse_unit(unit) in VOLUME_UNITS


def is_count(unit: Unit | str) -> bool:
    return parse_unit(unit) in COUNT_UNITS


def dimension(unit: Unit | str) -> str:
    """``"mass"``, ``"volume"`` or ``"count"`` — decides convertibility."""
    u = parse_unit(unit)
    if u in MASS_UNITS:
        return "mass"
    if u in VOLUME_UNITS:
        return "volume"
    return "count"


def base_unit(unit: Unit | str) -> Unit:
    """The base unit of a dimension: ``kg``, ``m3`` or ``EA``."""
    u = parse_unit(unit)
    if u in MASS_UNITS:
        return Unit.KG
    if u in VOLUME_UNITS:
        return Unit.M3
    return Unit.EA


@dataclass(frozen=True)
class ConversionBasis:
    """A density, with the provenance needed to defend it.

    ``kg_per_m3`` alone is not enough: two records can use different densities
    for the same material and both be legitimate. Recording where the number came
    from is what makes a converted quantity reviewable.
    """

    kg_per_m3: float
    source: str
    note: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.kg_per_m3) or self.kg_per_m3 <= 0:
            raise InvalidBasis(
                f"density must be a finite number greater than zero, got {self.kg_per_m3!r}"
            )
        if not (self.source or "").strip():
            raise InvalidBasis("a conversion basis must name its source")

    def as_dict(self) -> dict[str, Any]:
        return {"kg_per_m3": self.kg_per_m3, "source": self.source, "note": self.note}


@dataclass(frozen=True)
class Conversion:
    """The result of a conversion, carrying the basis it used."""

    amount: float
    unit: Unit
    original_amount: float
    original_unit: Unit
    #: Present only when the conversion crossed dimensions (needed a density).
    basis_used: ConversionBasis | None = None
    note: str = ""

    @property
    def changed(self) -> bool:
        return self.unit != self.original_unit or self.amount != self.original_amount

    def as_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "unit": self.unit.value,
            "original_amount": self.original_amount,
            "original_unit": self.original_unit.value,
            "conversion_basis": self.basis_used.as_dict() if self.basis_used else None,
            "note": self.note,
        }


def convert(
    amount: float,
    frm: Unit | str,
    to: Unit | str,
    *,
    basis: ConversionBasis | None = None,
) -> Conversion:
    """Convert ``amount`` from ``frm`` to ``to``, deterministically.

    Same-dimension conversions need nothing else. Cross-dimension conversions
    (mass ↔ volume) require ``basis`` and raise
    :class:`ConversionBasisRequired` without one.

    The returned :class:`Conversion` always reports the original value, so a
    caller that persists the result can persist its provenance in the same write.
    """
    source_unit = parse_unit(frm)
    target_unit = parse_unit(to)
    if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
        raise UnitError(f"amount must be a finite number, got {amount!r}")
    value = float(amount)

    if source_unit == target_unit:
        return Conversion(value, target_unit, value, source_unit)

    same_dimension = dimension(source_unit) == dimension(target_unit)
    if same_dimension:
        converted = value * _TO_BASE[source_unit] / _TO_BASE[target_unit]
        return Conversion(
            _round(converted),
            target_unit,
            value,
            source_unit,
            note=f"{source_unit.value} → {target_unit.value} (same dimension, exact factor)",
        )

    # Cross-dimension. Mass ↔ volume is bridged by a density; a count is not
    # bridgeable at all, and saying so is more useful than approximating it.
    if "count" in (dimension(source_unit), dimension(target_unit)):
        raise IncompatibleUnits(
            f"cannot convert {source_unit.value} → {target_unit.value}: a discrete item count has "
            f"no mass or volume equivalence in this system. Keep a counted item in EA and a fluid "
            f"in a mass or volume unit; if a per-item mass exists it belongs in the item's own "
            f"quality attributes, not in a unit conversion."
        )
    if basis is None:
        raise ConversionBasisRequired(
            f"{source_unit.value} → {target_unit.value} crosses mass and volume and needs a "
            f"density basis (kg_per_m3) for the specific material. Project 117 does not assume "
            f"a universal density."
        )
    density = basis.kg_per_m3
    if dimension(source_unit) == "volume":
        # volume → mass: kg = m³ × kg/m³
        in_base = value * _TO_BASE[source_unit]  # m³
        converted = in_base * density  # kg
    else:
        # mass → volume: m³ = kg ÷ (kg/m³)
        in_base = value * _TO_BASE[source_unit]  # kg
        converted = in_base / density  # m³
    converted = converted / _TO_BASE[target_unit]
    return Conversion(
        _round(converted),
        target_unit,
        value,
        source_unit,
        basis_used=basis,
        note=(
            f"{source_unit.value} → {target_unit.value} via density "
            f"{density:g} kg/m³ ({basis.source})"
        ),
    )


def _round(value: float) -> float:
    """Settle float noise without losing money.

    Six *decimal places*, deliberately not six significant figures. Significant
    figures scale with magnitude, so at ₹21,892.24 they keep only ~0.01 of
    precision and a cost of 2 × ₹10,946.12 came back as ₹21,892.20 — a real
    rounding loss on a currency figure. Decimal places are absolute: they clear
    binary-float artefacts (0.1 + 0.2) while preserving every paise, and no
    industrial quantity is measured below 1e-6 of its unit.
    """
    if value == 0:
        return 0.0
    return round(value, 6)


def convert_quantity(quantity: "Quantity", to: Unit | str) -> "Quantity":
    """Convert a :class:`Quantity`, keeping its basis when one was needed."""
    result = convert(quantity.amount, quantity.unit, to, basis=quantity.basis)
    return Quantity(result.amount, result.unit, basis=result.basis_used or quantity.basis)


def require_same_dimension(a: Unit | str, b: Unit | str, *, context: str = "") -> str:
    """Assert two units can be compared, and say why not when they cannot.

    Comparison is the operation where a silent mismatch does the most damage —
    "18 MT available, 4 KL required" is not a comparison, and a system that
    quietly subtracts them produces a number that looks like an answer.
    """
    da, db = dimension(a), dimension(b)
    if da != db:
        where = f" ({context})" if context else ""
        raise IncompatibleUnits(
            f"cannot compare {parse_unit(a).value} with {parse_unit(b).value}{where}: "
            f"{da} and {db} are different dimensions; convert to a common unit with an "
            f"explicit basis first"
        )
    return da


@dataclass(frozen=True)
class Quantity:
    """An amount with its unit and, for cross-dimension values, its basis.

    Immutable on purpose: a quantity that can be mutated in place is a quantity
    whose unit can drift away from its number.
    """

    amount: float
    unit: Unit
    basis: ConversionBasis | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(
        cls,
        amount: float,
        unit: Unit | str,
        *,
        basis: ConversionBasis | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> "Quantity":
        return cls(float(amount), parse_unit(unit), basis, dict(provenance or {}))

    def to(self, unit: Unit | str) -> "Quantity":
        return convert_quantity(self, unit)

    def add(self, other: "Quantity", *, to: Unit | str | None = None) -> "Quantity":
        """Add two quantities of the same dimension.

        Refuses across dimensions rather than coercing: adding a volume to a mass
        is a modelling error, not a unit error to paper over.
        """
        require_same_dimension(self.unit, other.unit, context="quantity addition")
        target = parse_unit(to) if to else self.unit
        left = self.to(target).amount
        right = other.to(target).amount
        return Quantity(_round(left + right), target, basis=self.basis or other.basis)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.amount:g} {UNIT_LABEL[self.unit]}"


# --------------------------------------------------------------------- pricing


@dataclass(frozen=True)
class Price:
    """A price per unit, with the currency and the unit it is quoted against.

    The unit is not decoration: ₹/kg and ₹/MT differ by a factor of 1000, and a
    price history that stores only the number is a price history that will be
    misread the first time two sources quote different bases.
    """

    amount: float
    currency: str
    per: Unit
    basis: ConversionBasis | None = None

    @classmethod
    def of(
        cls,
        amount: float,
        per: Unit | str,
        *,
        currency: str = "INR",
        basis: ConversionBasis | None = None,
    ) -> "Price":
        return cls(float(amount), currency.strip().upper() or "INR", parse_unit(per), basis)

    @property
    def price_unit(self) -> str:
        """``INR/MT`` — the full basis, never just the number."""
        return f"{self.currency}/{UNIT_LABEL[self.per]}"

    def per_unit(self, unit: Unit | str) -> "Price":
        """Re-base the price onto another unit.

        ₹/kg → ₹/MT is an exact factor. ₹/KL → ₹/MT is density-dependent and needs
        a basis, which this method supplies to :func:`convert` and lets that
        function adjudicate — one gatekeeper for every conversion in the system,
        rather than a second compatibility check here that could disagree with it.
        """
        target = parse_unit(unit)
        if target == self.per:
            return self
        # A price per smaller unit becomes a LARGER number per bigger unit:
        # ₹/kg × 1000 = ₹/MT. That is the inverse of a quantity conversion.
        one = convert(1.0, target, self.per, basis=self.basis)
        return Price(
            _round(self.amount * one.amount), self.currency, target, self.basis or one.basis_used
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "currency": self.currency,
            "per": self.per.value,
            "price_unit": f"{self.currency}/{UNIT_LABEL[self.per]}",
            "conversion_basis": self.basis.as_dict() if self.basis else None,
        }


def cost_of(quantity: Quantity, price: Price) -> tuple[float, dict[str, Any]]:
    """Deterministic cost: quantity × unit price, returned with its basis.

    Returns ``(amount, basis)`` where ``basis`` is a full description of the
    calculation, so a displayed cost can always be reconstructed from what is
    stored next to it.
    """
    # `per_unit` performs the compatibility check (via `convert`), so an
    # incompatible pair is refused there and a density-bridged pair is allowed.
    aligned = price.per_unit(quantity.unit)
    total = _round(quantity.amount * aligned.amount)
    return total, {
        "currency": price.currency,
        "quantity": quantity.amount,
        "quantity_unit": quantity.unit.value,
        "unit_price": aligned.amount,
        "unit_price_per": aligned.per.value,
        "formula": "quantity × unit_price",
        "conversion_basis": aligned.basis.as_dict() if aligned.basis else None,
    }


__all__ = [
    "Conversion",
    "ConversionBasis",
    "ConversionBasisRequired",
    "IncompatibleUnits",
    "InvalidBasis",
    "PRICE_UNITS",
    "Price",
    "Quantity",
    "Unit",
    "UnitError",
    "UnsupportedUnit",
    "UNIT_LABEL",
    "base_unit",
    "convert",
    "convert_quantity",
    "cost_of",
    "dimension",
    "COUNT_UNITS",
    "is_count",
    "is_mass",
    "is_volume",
    "parse_unit",
    "require_same_dimension",
]
