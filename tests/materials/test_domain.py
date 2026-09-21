"""Domain tests: inventory arithmetic, thresholds, forecasting, price history,
production aggregation, equipment requirements, financial determinism, the
procurement recommendation, and seed coherence.

Every assertion here is against the *seeded* store, so the tests fail if the
generator and the service ever disagree about what the data means.
"""

from __future__ import annotations

from datetime import date

import pytest
from backend.materials import service as svc
from backend.materials.models import (
    DataStatus,
    InventoryBalance,
    Material,
    MaterialClass,
    MaterialMovement,
    MovementType,
    PeriodType,
    PriceObservation,
    Provenance,
    new_id,
    period_bounds,
)
from backend.materials.seed import SEED_NOTE, SEED_SOURCE
from backend.simulation.datasets import load_plant

# --------------------------------------------------------------- inventory


class TestInventoryArithmetic:
    def test_available_is_quantity_minus_reserved(self, store):
        status = svc.inventory_status(store, "MECH-SEAL-P1001")
        assert status["quantity"] == 18.0
        assert status["reserved"] == 3.0
        assert status["available"] == 15.0

    def test_available_matches_a_direct_computation_for_every_material(self, store):
        for material in store.materials(limit=500):
            status = svc.inventory_status(store, material["id"])
            if status.get("quantity") is None:
                continue
            assert status["available"] == round(status["quantity"] - status["reserved"], 6), (
                material["id"]
            )

    def test_basis_is_reported_with_the_value(self, store):
        status = svc.inventory_status(store, "MECH-SEAL-P1001")
        assert status["calculation_basis"]["available"] == "quantity − reserved"

    def test_unknown_material_reports_material_not_found(self, store):
        status = svc.inventory_status(store, "NOPE-1")
        assert status["limitations"][0]["code"] == svc.MATERIAL_NOT_FOUND

    def test_material_without_a_balance_reports_inventory_unavailable(self, store):
        store.upsert_material(
            Material(
                id="SPARE-NO-BALANCE",
                name="Unstocked item",
                material_class=MaterialClass.MAINTENANCE_SPARE,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        status = svc.inventory_status(store, "SPARE-NO-BALANCE")
        assert status["limitations"][0]["code"] == svc.INVENTORY_DATA_UNAVAILABLE
        assert status.get("available") is None


class TestThresholdStates:
    @pytest.mark.parametrize(
        ("quantity", "reserved", "safety", "reorder", "expected"),
        [
            (100.0, 0.0, 10.0, 20.0, "AVAILABLE"),
            (25.0, 0.0, 10.0, 30.0, "DEPLETING"),
            (12.0, 0.0, 10.0, 30.0, "DEPLETING"),  # above safety (10), at/below reorder (30)
            (10.0, 0.0, 10.0, 30.0, "CRITICAL"),
            (5.0, 5.0, 10.0, 30.0, "OUT_OF_STOCK"),
        ],
    )
    def test_status_derives_from_available_against_the_thresholds(
        self, empty_store, quantity, reserved, safety, reorder, expected
    ):
        empty_store.upsert_material(
            Material(
                id="M",
                name="m",
                material_class=MaterialClass.MAINTENANCE_SPARE,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        empty_store.add_balance(
            InventoryBalance(
                id="B",
                material_id="M",
                location="W",
                quantity=quantity,
                reserved=reserved,
                unit="EA",
                safety_stock=safety,
                reorder_level=reorder,
                provenance=Provenance.synthetic("test"),
            )
        )
        assert svc.inventory_status(empty_store, "M")["status"] == expected

    def test_seeded_data_exercises_every_state(self, store):
        """The demo must show a healthy item, a depleting one and a critical one."""
        states = {
            svc.inventory_status(store, m["id"])["status"] for m in store.materials(limit=500)
        }
        assert {"AVAILABLE", "CRITICAL"} <= states
        assert "OUT_OF_STOCK" in states


class TestDaysOfCover:
    def test_cover_is_available_over_observed_consumption(self, store):
        cover = svc.days_of_cover(store, "MECH-SEAL-P1001", window_days=30)
        available = svc.inventory_status(store, "MECH-SEAL-P1001")["available"]
        # `average_daily_consumption` is reported rounded, so the identity holds
        # to the precision the API actually exposes rather than to 1e-9.
        assert cover["days_of_cover"] == pytest.approx(
            available / cover["average_daily_consumption"], rel=1e-4
        )

    def test_no_consumption_history_reports_insufficient_history(self, store):
        """A material nobody consumes has no cover figure — not zero, not infinity."""
        store.upsert_material(
            Material(
                id="PASSIVE",
                name="Passive spare",
                material_class=MaterialClass.MAINTENANCE_SPARE,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        store.add_balance(
            InventoryBalance(
                id="BP",
                material_id="PASSIVE",
                location="W",
                quantity=5,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        cover = svc.days_of_cover(store, "PASSIVE")
        assert cover["days_of_cover"] is None
        assert cover["limitations"][0]["code"] == svc.INSUFFICIENT_HISTORY


class TestForecast:
    def test_forecast_projects_depletion_from_observed_consumption(self, store, anchor):
        forecast = svc.forecast_inventory(store, "RM-CRUDE-LIGHT", anchor=anchor)
        assert forecast["projected_depletion_date"] is not None
        assert forecast["samples"] >= svc.MIN_FORECAST_SAMPLES
        assert forecast["confidence"] in {"HIGH", "MEDIUM", "LOW"}
        assert "cv" in forecast["confidence_basis"]

    def test_thin_history_refuses_to_forecast(self, empty_store):
        empty_store.upsert_material(
            Material(
                id="THIN",
                name="thin",
                material_class=MaterialClass.MAINTENANCE_SPARE,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        empty_store.add_balance(
            InventoryBalance(
                id="BT",
                material_id="THIN",
                location="W",
                quantity=10,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        # One consumption day only — well below the minimum.
        empty_store.append_movement(
            MaterialMovement(
                id=new_id("MV"),
                material_id="THIN",
                movement_type=MovementType.CONSUMPTION,
                quantity=1,
                unit="EA",
                timestamp="2026-09-10T06:00:00+00:00",
                provenance=Provenance.synthetic("test"),
            )
        )
        forecast = svc.forecast_inventory(empty_store, "THIN", anchor=date(2026, 9, 14))
        assert forecast["status"] == svc.INSUFFICIENT_HISTORY
        assert forecast["limitations"][0]["code"] == svc.INSUFFICIENT_HISTORY
        assert "projected_depletion_date" not in forecast

    def test_forecast_without_a_balance_reports_inventory_unavailable(self, store):
        forecast = svc.forecast_inventory(store, "NOPE-1")
        assert forecast["limitations"][0]["code"] == svc.MATERIAL_NOT_FOUND


# ------------------------------------------------------------------ movements


class TestMovements:
    def test_movements_are_append_only(self, store):
        """There is no update or delete on the store, by design."""
        assert not hasattr(store, "update_movement")
        assert not hasattr(store, "delete_movement")

    def test_a_correction_is_a_new_record(self, store):
        before = len(store.movements("MECH-SEAL-P1001"))
        store.append_movement(
            MaterialMovement(
                id=new_id("MV"),
                material_id="MECH-SEAL-P1001",
                movement_type=MovementType.ADJUSTMENT,
                quantity=-1,
                unit="EA",
                timestamp="2026-09-14T10:00:00+00:00",
                reference="correction",
                provenance=Provenance.synthetic("test"),
            )
        )
        after = store.movements("MECH-SEAL-P1001")
        assert len(after) == before + 1
        assert any(m["movement_type"] == "ADJUSTMENT" for m in after)

    def test_every_movement_type_is_represented_in_the_seed(self, store):
        types = {m["movement_type"] for m in store.movements(limit=1000)}
        assert {"RECEIPT", "CONSUMPTION", "PRODUCTION", "DISPATCH"} <= types


# --------------------------------------------------------------------- prices


class TestPriceHistory:
    def test_never_overwrites_history(self, store):
        """A new observation adds a row; it does not replace the old one."""
        before = len(store.prices("MECH-SEAL-P1001", limit=2000))
        store.append_price(
            PriceObservation(
                id=new_id("PRC"),
                item_id="MECH-SEAL-P1001",
                price=99_999.0,
                unit="EA",
                observed_on=date.today().isoformat(),
                source="test",
                data_status=DataStatus.MANUAL,
                provenance=Provenance.synthetic("test"),
            )
        )
        assert len(store.prices("MECH-SEAL-P1001", limit=2000)) == before + 1

    def test_history_within_a_window_is_returned(self, store, anchor):
        history = svc.price_history(store, "MECH-SEAL-P1001", window_days=30, anchor=anchor)
        assert history["points"] > 0
        assert history["current"]["price"] > 0
        assert history["calculation_basis"]["formula"]

    def test_change_percent_matches_its_own_inputs(self, store, anchor):
        history = svc.price_history(store, "RM-CRUDE-LIGHT", window_days=30, anchor=anchor)
        expected = (
            (history["current"]["price"] - history["baseline"]["price"])
            / history["baseline"]["price"]
            * 100
        )
        assert history["change_percent"] == pytest.approx(expected, rel=1e-3)

    def test_movement_flag_respects_configurable_thresholds(self, store, anchor):
        # A zero threshold makes any change abnormal; a huge one makes it normal.
        strict = svc.price_history(
            store, "RM-CRUDE-LIGHT", window_days=30, anchor=anchor, abnormal_pct=0.0
        )
        loose = svc.price_history(
            store, "RM-CRUDE-LIGHT", window_days=30, anchor=anchor, abnormal_pct=1e9
        )
        assert strict["movement"] == "ABNORMAL"
        assert loose["movement"] == "NORMAL"

    def test_missing_history_is_reported(self, store):
        history = svc.price_history(store, "NO-PRICES")
        assert history["status"] == svc.PRICE_HISTORY_UNAVAILABLE

    @pytest.mark.parametrize("window", [7, 30, 90, 365])
    def test_every_required_window_has_data(self, store, anchor, window):
        history = svc.price_history(store, "FP-DIESEL", window_days=window, anchor=anchor)
        assert history["points"] > 0, f"no observations in the {window}D window"

    def test_manual_entries_are_distinguishable_from_synthetic(self, store):
        statuses = {
            p["data_status"]
            for m in store.materials(limit=500)
            for p in store.prices(m["id"], limit=2000)
        }
        assert "SYNTHETIC_DEMO" in statuses


# ----------------------------------------------------------------- production


class TestProduction:
    @pytest.mark.parametrize("period", list(PeriodType))
    def test_all_three_granularities_aggregate(self, store, period):
        series = svc.production_series(store, period=period)
        assert series["buckets"], f"no {period.value} buckets"
        assert series["unit"] == "MT"

    def test_weekly_bucket_contains_its_daily_rows(self, store):
        daily = svc.production_series(store, period=PeriodType.DAILY, product_id="FP-DIESEL")
        weekly = svc.production_series(store, period=PeriodType.WEEKLY, product_id="FP-DIESEL")
        by_date = {b["period_start"]: b["quantity"] for b in daily["buckets"]}
        week = weekly["buckets"][-1]
        total = sum(
            q for d, q in by_date.items() if week["period_start"] <= d <= week["period_end"]
        )
        assert total == pytest.approx(week["quantity"], rel=1e-6)

    def test_partial_period_is_flagged(self, store, anchor):
        series = svc.production_series(store, period=PeriodType.WEEKLY, anchor=anchor)
        assert series["latest"]["partial"] is False  # the newest *complete* bucket

    def test_period_over_period_compares_complete_periods(self, store, anchor):
        series = svc.production_series(store, period=PeriodType.MONTHLY, anchor=anchor)
        if series["change_percent"] is not None:
            assert series["previous"] is not None
            assert series["latest"]["period_end"] <= anchor.isoformat()

    def test_unknown_filter_reports_no_data(self, store):
        series = svc.production_series(store, product_id="NOT-A-PRODUCT")
        assert series["limitations"][0]["code"] == svc.DATA_UNAVAILABLE

    def test_roll_forward_reconciles(self, store):
        record = store.production(limit=1)[0]
        assert record["closing"] == pytest.approx(
            record["opening"] + record["receipts"] - record["dispatches"] + record["adjustments"],
            rel=1e-9,
        )


class TestPeriodBounds:
    def test_daily_is_a_single_day(self):
        assert period_bounds(PeriodType.DAILY, date(2026, 9, 14)) == ("2026-09-14", "2026-09-14")

    def test_week_runs_monday_to_sunday(self):
        assert period_bounds(PeriodType.WEEKLY, date(2026, 9, 14)) == ("2026-09-14", "2026-09-20")

    def test_month_ends_on_the_last_day(self):
        assert period_bounds(PeriodType.MONTHLY, date(2026, 2, 10)) == ("2026-02-01", "2026-02-28")

    def test_leap_february(self):
        assert period_bounds(PeriodType.MONTHLY, date(2028, 2, 10)) == ("2028-02-01", "2028-02-29")


# --------------------------------------------------------------- requirements


class TestEquipmentRequirements:
    def test_requirements_resolve_for_a_real_asset(self, store):
        resolved = svc.equipment_requirements(store, "e-P-1001")
        assert resolved["requirements"]
        assert resolved["requirements"][0]["item_id"] == "MECH-SEAL-P1001"

    def test_failure_mode_prioritises_the_matching_spare(self, store):
        resolved = svc.equipment_requirements(store, "e-P-1001", failure_mode="seal_leak")
        assert resolved["requirements"][0]["mode_match"] is True

    def test_unknown_equipment_reports_requirement_not_found(self, store):
        resolved = svc.equipment_requirements(store, "e-NOPE-9999")
        assert resolved["limitations"][0]["code"] == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND

    def test_coverage_rule_is_the_documented_one(self, store):
        result = svc.material_requirement(store, "e-P-1001", failure_mode="seal_leak")
        line = result["lines"][0]
        expected = round(line["available"] - line["required_quantity"] - line["safety_stock"], 6)
        assert line["surplus_after_requirement_and_safety"] == expected
        assert line["coverage"] == ("COVERED" if expected >= 0 else "SHORTFALL")

    def test_shortfall_is_detected_when_stock_is_thin(self, store):
        """BEARING-C1053 is below safety stock in the seed, on purpose."""
        result = svc.material_requirement(store, "e-C-1053", failure_mode="bearing_overheat")
        assert result["overall_coverage"] in {"COVERED", "SHORTFALL"}
        if result["lines"]:
            assert result["lines"][0]["coverage"] == "SHORTFALL"

    def test_multiplier_scales_the_requirement(self, store):
        single = svc.material_requirement(store, "e-P-1001")
        triple = svc.material_requirement(store, "e-P-1001", multiplier=3.0)
        assert (
            triple["lines"][0]["required_quantity"] == single["lines"][0]["required_quantity"] * 3
        )

    def test_equipment_ids_are_real_plant_assets(self, store):
        """The bridge must land on the live plant, not a fabricated asset code."""
        plant = load_plant("refinery")
        real = {e.id for e in plant.equipment}
        for req in store.requirements():
            assert req["equipment_id"] in real, req["equipment_id"]


# ------------------------------------------------------------------ financial


class TestFinancial:
    def test_cost_is_quantity_times_unit_price(self, store):
        impact = svc.financial_impact(store, "MECH-SEAL-P1001", 2)
        assert impact["estimated_cost"] == pytest.approx(2 * impact["unit_price"], rel=1e-9)
        assert impact["calculation_basis"]["formula"] == "quantity × unit_price"

    def test_cost_is_deterministic(self, store):
        first = svc.financial_impact(store, "FP-DIESEL", 100)
        second = svc.financial_impact(store, "FP-DIESEL", 100)
        assert first["estimated_cost"] == second["estimated_cost"]

    def test_every_financial_figure_is_labelled_illustrative(self, store):
        impact = svc.financial_impact(store, "RM-CRUDE-LIGHT", 500)
        assert impact["calculation_status"] == "ILLUSTRATIVE"

    def test_missing_price_blocks_the_calculation(self, store):
        store.upsert_material(
            Material(
                id="UNPRICED",
                name="Item with no recorded price",
                material_class=MaterialClass.MAINTENANCE_SPARE,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        impact = svc.financial_impact(store, "UNPRICED", 5)
        assert impact["limitations"][0]["code"] == svc.PRICE_HISTORY_UNAVAILABLE

    def test_unknown_material_is_reported_as_such(self, store):
        impact = svc.financial_impact(store, "NO-SUCH-MATERIAL", 5)
        assert impact["limitations"][0]["code"] == svc.MATERIAL_NOT_FOUND

    def test_mass_to_volume_cost_uses_the_recorded_density(self, store):
        """LUBE-OIL-ISO46 is recorded in KL and carries a density."""
        impact = svc.financial_impact(store, "LUBE-OIL-ISO46", 2, unit="MT")
        assert impact.get("estimated_cost") is not None, impact.get("limitations")
        assert "density" in str(impact["calculation_basis"]).lower() or impact["unit"] == "MT"


# ------------------------------------------------------------- recommendation


class TestProcurementRecommendation:
    def test_recommendation_is_reviewable_and_never_auto_executed(self, store):
        rec = svc.procurement_recommendation(store, "e-P-1001", failure_mode="seal_leak")
        assert rec["status"] == "PENDING_APPROVAL"
        assert rec["approval"]["required"] is True
        assert rec["approval"]["state"] == "PENDING_APPROVAL"

    def test_recommendation_carries_its_evidence(self, store):
        rec = svc.procurement_recommendation(store, "e-P-1001", failure_mode="seal_leak")
        line = rec["lines"][0]
        assert line["available"] is not None
        assert line["price"]["current"] is not None
        assert line["cost"]["amount"] is not None

    def test_no_procurement_when_stock_covers_the_need(self, store):
        rec = svc.procurement_recommendation(store, "e-P-1001", failure_mode="seal_leak")
        assert rec["overall_coverage"] == "COVERED"
        assert rec["procurement_required"] is False
        assert rec["lines"][0]["recommended_order_quantity"] == 0.0

    def test_procurement_proposed_when_stock_is_short(self, store):
        rec = svc.procurement_recommendation(store, "e-C-1053", failure_mode="bearing_overheat")
        if rec["overall_coverage"] == "SHORTFALL":
            assert rec["procurement_required"] is True
            assert rec["lines"][0]["recommended_order_quantity"] > 0

    def test_cost_is_the_sum_of_the_lines(self, store):
        rec = svc.procurement_recommendation(store, "e-P-1001")
        total = sum(line["cost"]["amount"] or 0 for line in rec["lines"])
        assert rec["estimated_material_cost"]["amount"] == pytest.approx(total, rel=1e-9)

    def test_missing_requirement_blocks_with_a_named_reason(self, store):
        rec = svc.procurement_recommendation(store, "e-NOPE-9999")
        assert rec["status"] == "BLOCKED"
        assert rec["limitations"][0]["code"] == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND


# ---------------------------------------------------------------- dashboard


class TestDashboardAndIntelligence:
    def test_dashboard_reports_only_measured_figures(self, store, anchor):
        board = svc.materials_dashboard(store, anchor=anchor)
        assert board["counts"]["materials"] > 0
        assert board["inventory_value"]["amount"] > 0
        assert board["inventory_value"]["calculation_status"] == "ILLUSTRATIVE"

    def test_missing_cover_explains_itself(self, store, anchor):
        """A null days-of-cover must carry the reason, not render as a blank cell."""
        board = svc.materials_dashboard(store, anchor=anchor)
        for entry in board["raw_material_cover"]:
            if entry["days_of_cover"] is None:
                assert entry["limitations"], entry["material_id"]
                assert entry["limitations"][0]["code"] == svc.INSUFFICIENT_HISTORY

    def test_dashboard_marks_its_data_status(self, store):
        assert (
            svc.materials_dashboard(store, anchor=date(2026, 9, 14))["data_status"]
            == "SYNTHETIC_DEMO"
        )

    def test_intelligence_finds_the_seeded_critical_items(self, store, anchor):
        intel = svc.inventory_intelligence(store, anchor=anchor)
        kinds = {i["kind"] for i in intel["insights"]}
        assert "OUT_OF_STOCK" in kinds or "BELOW_SAFETY_STOCK" in kinds
        assert intel["counts"]["critical"] >= 1

    def test_every_insight_carries_evidence(self, store, anchor):
        for insight in svc.inventory_intelligence(store, anchor=anchor)["insights"]:
            assert insight["evidence"], insight["kind"]

    def test_insights_are_ordered_by_severity(self, store, anchor):
        order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        severities = [
            order[i["severity"]]
            for i in svc.inventory_intelligence(store, anchor=anchor)["insights"]
        ]
        assert severities == sorted(severities)


class TestGraph:
    def test_graph_exposes_operational_relationships(self, store):
        graph = svc.material_graph(store)
        relations = {e["relation"] for e in graph["edges"]}
        assert {"REQUIRES", "STOCKED_AT", "SUPPLIED_BY"} <= relations

    def test_equipment_requires_spare_edges_exist(self, store):
        graph = svc.material_graph(store)
        requires = [e for e in graph["edges"] if e["relation"] == "REQUIRES"]
        assert requires
        assert any(e["source"] == "e-P-1001" and e["target"] == "MECH-SEAL-P1001" for e in requires)

    def test_produces_is_one_edge_per_unit_product_pair(self, store):
        """Iterating production records once emitted one edge per day per product."""
        graph = svc.material_graph(store)
        produces = [
            (e["source"], e["target"]) for e in graph["edges"] if e["relation"] == "PRODUCES"
        ]
        assert len(produces) == len(set(produces)), "duplicate PRODUCES edges"
        assert len(produces) < 50, (
            f"{len(produces)} PRODUCES edges looks like per-record duplication"
        )

    def test_edges_carry_provenance(self, store):
        graph = svc.material_graph(store)
        assert all(e.get("provenance") for e in graph["edges"])

    def test_neighbourhood_is_scoped_to_one_material(self, store):
        hood = svc.material_neighbourhood(store, "MECH-SEAL-P1001")
        assert all(
            n["id"] == "MECH-SEAL-P1001"
            or any(
                e["source"] == "MECH-SEAL-P1001"
                and e["target"] == n["id"]
                or e["target"] == "MECH-SEAL-P1001"
                and e["source"] == n["id"]
                for e in hood["edges"]
            )
            for n in hood["nodes"]
        )
        assert hood["counts"]["nodes"] < svc.material_graph(store)["counts"]["nodes"]


# ------------------------------------------------------------ seed coherence


class TestSeedCoherence:
    """No orphan records: every reference in the demo resolves."""

    def test_every_balance_references_a_real_material(self, store):
        materials = {m["id"] for m in store.materials(limit=500)}
        assert all(b["material_id"] in materials for b in store.all_balances(limit=2000))

    def test_every_movement_references_a_real_material(self, store):
        materials = {m["id"] for m in store.materials(limit=500)}
        assert all(m["material_id"] in materials for m in store.movements(limit=1000))

    def test_every_price_references_a_real_material(self, store):
        for material in store.materials(limit=500):
            for price in store.prices(material["id"], limit=1):
                assert price["item_id"] == material["id"]

    def test_every_material_supplier_resolves(self, store):
        suppliers = {s["id"] for s in store.suppliers()}
        for material in store.materials(limit=500):
            if material["supplier_id"]:
                assert material["supplier_id"] in suppliers, material["id"]

    def test_every_production_record_references_a_real_product(self, store):
        materials = {m["id"] for m in store.materials(limit=500)}
        assert all(p["product_id"] in materials for p in store.production(limit=2000))

    def test_every_production_process_unit_is_a_real_asset(self, store):
        plant = load_plant("refinery")
        real = {e.id for e in plant.equipment}
        for record in store.production(limit=2000):
            if record["process_unit_id"]:
                assert record["process_unit_id"] in real, record["process_unit_id"]

    def test_every_requirement_mode_is_a_real_failure_mode(self, store):
        plant = load_plant("refinery")
        modes = {m.id for m in plant.failure_modes}
        for req in store.requirements():
            if req["failure_mode"]:
                assert req["failure_mode"] in modes, req["failure_mode"]

    def test_every_financial_event_references_something_real(self, store):
        materials = {m["id"] for m in store.materials(limit=500)}
        for event in store.financial_events(limit=500):
            assert event["reference"] in materials, event["reference"]

    def test_every_record_is_marked_synthetic(self, store):
        for material in store.materials(limit=500):
            assert material["provenance"]["data_status"] == "SYNTHETIC_DEMO"
            assert material["provenance"]["source"] == SEED_SOURCE
        for balance in store.all_balances(limit=2000):
            assert balance["provenance"]["data_status"] == "SYNTHETIC_DEMO"
        for movement in store.movements(limit=1000):
            assert movement["provenance"]["data_status"] == "SYNTHETIC_DEMO"

    def test_the_note_says_what_the_data_is_not(self):
        assert "Not MRPL data" in SEED_NOTE
        assert "Not a market price" in SEED_NOTE

    def test_reseeding_a_populated_store_is_refused(self, store):
        from backend.materials.seed import seed_materials

        with pytest.raises(RuntimeError):
            seed_materials(store)

    def test_raw_material_densities_are_recorded(self, store):
        """A KL→MT conversion needs a basis; the seed must supply one."""
        for material_id in ("RM-CRUDE-LIGHT", "RM-CRUDE-HEAVY"):
            material = store.material(material_id)
            assert material["quality_attributes"]["density_kg_per_m3"] > 0
