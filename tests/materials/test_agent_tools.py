"""Tests for the materials agent tools.

The property under test is not "the tool returns something" but "the tool returns
what the domain service computed, and nothing else". An agent that can only read
backend-computed values cannot fabricate an inventory position; these tests pin
that contract, including the cases where the honest answer is a limitation code
rather than a number.
"""

from __future__ import annotations

import asyncio

import pytest
from backend.materials import service as svc
from backend.tools.base import ToolContext, ToolUnavailable
from backend.tools.materials import MATERIALS_TOOL_CLASSES, MATERIALS_TOOL_NAMES


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def context(store) -> ToolContext:
    return ToolContext(user="test", roles=["operator"], materials=store)


def tool_for(name: str):
    for cls in MATERIALS_TOOL_CLASSES:
        instance = cls()
        if instance.spec.name == name:
            return instance
    raise AssertionError(f"no tool named {name}")


class TestRegistration:
    def test_all_required_tools_are_declared(self):
        required = {
            "get_material",
            "get_inventory_status",
            "get_material_movements",
            "get_production_output",
            "get_equipment_material_requirements",
            "get_maintenance_requirements",
            "search_price_history",
            "calculate_material_requirement",
            "forecast_inventory",
            "generate_procurement_recommendation",
        }
        assert required == set(MATERIALS_TOOL_NAMES)

    def test_every_materials_tool_is_read_only(self):
        """No materials tool may write, order or approve anything."""
        for cls in MATERIALS_TOOL_CLASSES:
            spec = cls().spec
            assert spec.risk.value == "read", f"{spec.name} is {spec.risk}"
            assert "execute" not in spec.capabilities

    def test_tools_are_registered_in_the_default_registry(self):
        from backend.tools.builtin import DEFAULT_TOOL_NAMES

        assert set(MATERIALS_TOOL_NAMES) <= set(DEFAULT_TOOL_NAMES)

    def test_every_tool_declares_input_and_output_schemas(self):
        for cls in MATERIALS_TOOL_CLASSES:
            spec = cls().spec
            assert spec.input_schema, spec.name
            assert spec.output_schema, spec.name
            assert spec.description


class TestMissingStore:
    def test_a_deployment_without_the_domain_refuses_clearly(self):
        ctx = ToolContext(user="t", roles=["operator"], materials=None)
        with pytest.raises(ToolUnavailable) as exc:
            run(
                tool_for("get_material").run(
                    tool_for("get_material").arguments_model(material_id="X"), ctx
                )
            )
        assert "materials domain is not available" in str(exc.value)


class TestReadsMatchTheDomain:
    def test_inventory_tool_returns_what_the_service_computed(self, store, context):
        expected = svc.inventory_status(store, "MECH-SEAL-P1001")
        result = run(
            tool_for("get_inventory_status").run(
                tool_for("get_inventory_status").arguments_model(material_id="MECH-SEAL-P1001"),
                context,
            )
        )
        assert result.status == "ok"
        assert result.output["available"] == expected["available"]
        assert result.output["reserved"] == expected["reserved"]
        assert result.output["status"] == expected["status"]

    def test_material_tool_returns_the_record(self, store, context):
        tool = tool_for("get_material")
        result = run(tool.run(tool.arguments_model(material_id="RM-CRUDE-LIGHT"), context))
        assert result.output["material"]["material_class"] == "RAW_MATERIAL"
        assert result.output["material"]["unit"] == "MT"
        assert result.output["data_status"] == "SYNTHETIC_DEMO"

    def test_movements_tool_returns_the_ledger(self, store, context):
        tool = tool_for("get_material_movements")
        result = run(tool.run(tool.arguments_model(material_id="MECH-SEAL-P1001"), context))
        assert result.output["count"] >= 1
        assert all(m["material_id"] == "MECH-SEAL-P1001" for m in result.output["items"])

    def test_production_tool_aggregates(self, context):
        tool = tool_for("get_production_output")
        result = run(tool.run(tool.arguments_model(period="WEEKLY"), context))
        assert result.output["period"] == "WEEKLY"
        assert result.output["buckets"]

    def test_production_tool_rejects_an_unknown_period(self, context):
        tool = tool_for("get_production_output")
        result = run(tool.run(tool.arguments_model(period="FORTNIGHTLY"), context))
        assert result.status == "invalid_arguments"

    def test_price_tool_returns_the_stored_series(self, store, context):
        tool = tool_for("search_price_history")
        result = run(
            tool.run(tool.arguments_model(item_id="MECH-SEAL-P1001", window_days=30), context)
        )
        assert result.output["current"]["price"] > 0
        assert result.output["points"] > 0
        assert result.output["data_status"] in {"SYNTHETIC_DEMO", "MANUAL"}

    def test_equipment_requirement_tool_ranks_the_matching_mode_first(self, context):
        tool = tool_for("get_equipment_material_requirements")
        result = run(
            tool.run(
                tool.arguments_model(equipment_id="e-P-1001", failure_mode="seal_leak"), context
            )
        )
        assert result.output["requirements"][0]["mode_match"] is True

    def test_forecast_tool_returns_a_limitation_rather_than_a_guess(self, empty_store):
        from backend.materials.models import InventoryBalance, Material, MaterialClass, Provenance

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
                id="B",
                material_id="THIN",
                location="W",
                quantity=5,
                unit="EA",
                provenance=Provenance.synthetic("test"),
            )
        )
        ctx = ToolContext(user="t", roles=["operator"], materials=empty_store)
        tool = tool_for("forecast_inventory")
        result = run(tool.run(tool.arguments_model(material_id="THIN"), ctx))
        assert result.output["status"] == svc.INSUFFICIENT_HISTORY
        assert "projected_depletion_date" not in result.output
        assert result.output["limitations"][0]["code"] == svc.INSUFFICIENT_HISTORY


class TestRecommendationTool:
    def test_recommendation_is_a_proposal_not_an_action(self, context):
        tool = tool_for("generate_procurement_recommendation")
        result = run(tool.run(tool.arguments_model(equipment_id="e-P-1001"), context))
        assert result.output["status"] == "PENDING_APPROVAL"
        assert result.output["approval"]["required"] is True

    def test_recommendation_carries_evidence_and_cost(self, context):
        tool = tool_for("generate_procurement_recommendation")
        result = run(tool.run(tool.arguments_model(equipment_id="e-P-1001"), context))
        line = result.output["lines"][0]
        assert line["available"] is not None
        assert line["price"]["current"] is not None
        assert result.output["estimated_material_cost"]["amount"] > 0

    def test_calculate_requirement_tool_quantifies_and_prices(self, context):
        tool = tool_for("calculate_material_requirement")
        result = run(
            tool.run(
                tool.arguments_model(
                    equipment_id="e-P-1001", failure_mode="seal_leak", multiplier=2.0
                ),
                context,
            )
        )
        line = result.output["lines"][0]
        assert line["required_quantity"] == 4.0  # 2 required × multiplier 2
        assert line["cost"]["estimated_cost"] is not None
        assert result.output["estimated_total_cost"]["calculation_status"] == "ILLUSTRATIVE"

    def test_a_missing_requirement_is_reported_not_invented(self, context):
        tool = tool_for("generate_procurement_recommendation")
        result = run(tool.run(tool.arguments_model(equipment_id="e-NOPE-9999"), context))
        assert result.status == "not_found"
        assert result.output["limitations"][0]["code"] == svc.MAINTENANCE_REQUIREMENT_NOT_FOUND


class TestKillerWorkflowEndToEnd:
    """EQUIPMENT → requirement → spare → inventory → price → cost → recommendation."""

    def test_the_whole_chain_runs_on_real_domain_calls(self, store, context):
        order = [
            ("get_material", {"material_id": "MECH-SEAL-P1001"}),
            (
                "get_equipment_material_requirements",
                {"equipment_id": "e-P-1001", "failure_mode": "seal_leak"},
            ),
            ("get_inventory_status", {"material_id": "MECH-SEAL-P1001"}),
            (
                "get_maintenance_requirements",
                {"equipment_id": "e-P-1001", "failure_mode": "seal_leak"},
            ),
            ("search_price_history", {"item_id": "MECH-SEAL-P1001", "window_days": 30}),
            (
                "calculate_material_requirement",
                {"equipment_id": "e-P-1001", "failure_mode": "seal_leak"},
            ),
            ("forecast_inventory", {"material_id": "MECH-SEAL-P1001"}),
            ("generate_procurement_recommendation", {"equipment_id": "e-P-1001"}),
        ]
        results = {}
        for name, args in order:
            tool = tool_for(name)
            outcome = run(tool.run(tool.arguments_model(**args), context))
            assert outcome.status in {"ok", "not_found"}, f"{name}: {outcome.error}"
            results[name] = outcome.output

        # The chain is internally consistent: the coverage the requirement tool
        # reports is the one the recommendation tool acted on.
        coverage = results["get_maintenance_requirements"]["lines"][0]
        recommendation = results["generate_procurement_recommendation"]["lines"][0]
        assert recommendation["item_id"] == coverage["item_id"]
        assert recommendation["coverage"] == coverage["coverage"]
        assert recommendation["available"] == coverage["available"]

        # And the cost is the required quantity times the stored unit price.
        calc = results["calculate_material_requirement"]["lines"][0]
        assert calc["cost"]["estimated_cost"] == pytest.approx(
            calc["required_quantity"] * calc["cost"]["unit_price"], rel=1e-6
        )

    def test_no_tool_can_write_to_the_store(self, store, context):
        """Every materials tool is a read; the store is unchanged afterwards."""
        before = store.counts()
        for cls in MATERIALS_TOOL_CLASSES:
            tool = cls()
            model = tool.arguments_model
            fields = set(model.model_fields)
            kwargs = {}
            if "material_id" in fields:
                kwargs["material_id"] = "MECH-SEAL-P1001"
            if "item_id" in fields:
                kwargs["item_id"] = "MECH-SEAL-P1001"
            if "equipment_id" in fields:
                kwargs["equipment_id"] = "e-P-1001"
            result = run(tool.run(model(**kwargs), context))
            assert result.status in {"ok", "not_found", "invalid_arguments"}, tool.spec.name
        assert store.counts() == before
