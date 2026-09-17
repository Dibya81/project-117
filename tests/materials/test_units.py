"""Deterministic unit-system tests.

The unit system is the foundation every inventory and financial figure rests on,
so these tests are about refusals as much as conversions: a converter that
silently guesses a density corrupts every number downstream of it.
"""

from __future__ import annotations

import pytest
from backend.materials.units import (
    ConversionBasis,
    ConversionBasisRequired,
    IncompatibleUnits,
    InvalidBasis,
    Price,
    Quantity,
    UnsupportedUnit,
    convert,
    cost_of,
    dimension,
    parse_unit,
)

DENSITY = ConversionBasis(kg_per_m3=850.0, source="test fixture", note="synthetic")


class TestSameDimension:
    def test_mt_to_kg_is_exact(self):
        assert convert(2, "MT", "kg").amount == 2000.0

    def test_kg_to_tonne_is_exact(self):
        assert convert(1500, "kg", "tonne").amount == 1.5

    def test_tonne_and_mt_are_interchangeable(self):
        """Both spellings mean the metric ton, so this is a fact, not a guess."""
        assert convert(3, "tonne", "MT").amount == 3.0

    def test_kl_and_m3_are_interchangeable(self):
        """1 kL ≡ 1 m³ by the SI definition of the litre — no density involved."""
        assert convert(7.5, "KL", "m3").amount == 7.5

    def test_identity_keeps_original(self):
        result = convert(5, "MT", "MT")
        assert result.amount == 5.0
        assert result.original_unit.value == "MT"
        assert result.basis_used is None

    def test_original_unit_is_always_reported(self):
        result = convert(2, "MT", "kg")
        assert result.original_amount == 2
        assert result.original_unit.value == "MT"
        assert result.unit.value == "kg"


class TestCrossDimensionRefusal:
    def test_kl_to_mt_without_basis_is_refused(self):
        """The headline rule: no universal density exists, so none is assumed."""
        with pytest.raises(ConversionBasisRequired) as exc:
            convert(10, "KL", "MT")
        assert "density basis" in str(exc.value)

    def test_mt_to_kl_without_basis_is_refused(self):
        with pytest.raises(ConversionBasisRequired):
            convert(10, "MT", "KL")

    def test_refusal_names_both_units(self):
        with pytest.raises(ConversionBasisRequired) as exc:
            convert(1, "KL", "kg")
        message = str(exc.value)
        assert "KL" in message and "kg" in message

    def test_with_basis_the_conversion_is_exact(self):
        # 10 m³ at 850 kg/m³ = 8 500 kg = 8.5 MT
        assert convert(10, "KL", "MT", basis=DENSITY).amount == 8.5

    def test_mass_to_volume_uses_the_inverse(self):
        # 8.5 MT at 850 kg/m³ = 10 m³ = 10 KL
        assert convert(8.5, "MT", "KL", basis=DENSITY).amount == 10.0

    def test_basis_is_returned_with_the_result(self):
        result = convert(10, "KL", "MT", basis=DENSITY)
        assert result.basis_used is DENSITY
        assert result.basis_used.as_dict()["kg_per_m3"] == 850.0
        assert "850" in result.note


class TestBasisValidation:
    def test_zero_density_is_rejected(self):
        with pytest.raises(InvalidBasis):
            ConversionBasis(kg_per_m3=0, source="x")

    def test_negative_density_is_rejected(self):
        with pytest.raises(InvalidBasis):
            ConversionBasis(kg_per_m3=-5, source="x")

    def test_non_finite_density_is_rejected(self):
        with pytest.raises(InvalidBasis):
            ConversionBasis(kg_per_m3=float("nan"), source="x")

    def test_basis_must_name_a_source(self):
        """An unattributed density cannot be reviewed, so it is not accepted."""
        with pytest.raises(InvalidBasis):
            ConversionBasis(kg_per_m3=850.0, source="   ")


class TestCountDimension:
    def test_ea_is_its_own_dimension(self):
        assert dimension("EA") == "count"
        assert dimension("MT") == "mass"
        assert dimension("KL") == "volume"

    def test_ea_to_ea_is_identity(self):
        assert convert(4, "EA", "EA").amount == 4.0

    def test_count_never_converts_to_mass(self):
        """A seal has no mass in this system; inventing one would be fiction."""
        with pytest.raises(IncompatibleUnits):
            convert(4, "EA", "kg")

    def test_count_never_converts_to_volume(self):
        with pytest.raises(IncompatibleUnits):
            convert(4, "EA", "KL")

    def test_a_basis_does_not_unlock_count_conversion(self):
        """Supplying a density must not make an EA→kg conversion succeed."""
        with pytest.raises(IncompatibleUnits):
            convert(4, "EA", "kg", basis=DENSITY)


class TestUnitParsing:
    def test_unknown_unit_is_rejected(self):
        with pytest.raises(UnsupportedUnit):
            parse_unit("barrels")

    def test_empty_unit_is_rejected(self):
        with pytest.raises(UnsupportedUnit):
            parse_unit("")

    @pytest.mark.parametrize("text", ["m3", "m³", "cum", "KL"])
    def test_volume_spellings(self, text):
        assert dimension(text) == "volume"

    @pytest.mark.parametrize("text", ["EA", "ea", "nos", "pcs", "each"])
    def test_count_spellings(self, text):
        assert dimension(text) == "count"


class TestQuantity:
    def test_addition_of_same_dimension(self):
        total = Quantity.of(2, "MT").add(Quantity.of(500, "kg"))
        assert total.amount == 2.5
        assert total.unit.value == "MT"

    def test_addition_across_dimensions_is_refused(self):
        with pytest.raises(IncompatibleUnits):
            Quantity.of(2, "MT").add(Quantity.of(5, "KL"))

    def test_conversion_preserves_basis(self):
        q = Quantity.of(10, "KL", basis=DENSITY)
        assert q.to("MT").amount == 8.5


class TestPrice:
    def test_price_per_unit_rebasing_is_exact(self):
        assert Price.of(72.5, "kg").per_unit("MT").amount == 72_500.0

    def test_price_in_the_other_direction(self):
        assert Price.of(72_500, "MT").per_unit("kg").amount == 72.5

    def test_price_rebasing_across_dimensions_needs_a_basis(self):
        with pytest.raises(ConversionBasisRequired):
            Price.of(96_000, "KL").per_unit("MT")

    def test_price_rebasing_across_dimensions_with_a_basis(self):
        # ₹96 000/KL at 880 kg/m³ → 1 MT occupies 1/0.88 KL = 1.1364 KL
        price = Price.of(96_000, "KL", basis=ConversionBasis(880.0, "test")).per_unit("MT")
        assert price.amount == pytest.approx(109_090.91, rel=1e-4)

    def test_price_unit_string_names_the_basis_unit(self):
        assert Price.of(100, "MT").price_unit == "INR/MT"


class TestCost:
    def test_cost_is_quantity_times_unit_price(self):
        total, basis = cost_of(Quantity.of(10, "MT"), Price.of(72.5, "kg"))
        assert total == 725_000.0
        assert basis["formula"] == "quantity × unit_price"
        assert basis["unit_price"] == 72_500.0

    def test_cost_refuses_mass_against_volume_without_a_basis(self):
        """10 MT priced per KL is not computable without knowing the density."""
        with pytest.raises(ConversionBasisRequired):
            cost_of(Quantity.of(10, "MT"), Price.of(50, "KL"))

    def test_cost_refuses_a_counted_item_against_a_mass_price(self):
        with pytest.raises(IncompatibleUnits):
            cost_of(Quantity.of(10, "EA"), Price.of(50, "MT"))

    def test_cost_bridges_mass_and_volume_when_a_basis_is_given(self):
        price = Price.of(96_000, "KL", basis=ConversionBasis(880.0, "test"))
        total, _ = cost_of(Quantity.of(10, "MT"), price)
        assert total == pytest.approx(1_090_909.09, rel=1e-6)

    def test_cost_is_deterministic_across_calls(self):
        a, _ = cost_of(Quantity.of(3.5, "MT"), Price.of(48_200, "MT"))
        b, _ = cost_of(Quantity.of(3.5, "MT"), Price.of(48_200, "MT"))
        assert a == b
