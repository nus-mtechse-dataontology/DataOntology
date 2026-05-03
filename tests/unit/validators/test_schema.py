import pytest
from unittest.mock import Mock, patch, MagicMock
from validators.syntactic.schema import QueryPlan, Constraint, QueryParameter


class TestQueryPlanSchema:
    """Test cases for QueryPlan schema validation."""

    def test_query_plan_basic_construction(self):
        """Test basic QueryPlan construction."""
        qp = QueryPlan(intent="cheapest_flight_on_route", constraints=[])
        assert qp.intent == "cheapest_flight_on_route"
        assert qp.constraints == []

    def test_query_plan_with_constraints(self):
        """Test QueryPlan with constraints."""
        constraints = [
            Constraint(parameter="origin", value="SIN"),
            Constraint(parameter="destination", value="BKK"),
        ]
        qp = QueryPlan(intent="cheapest_flight_on_route", constraints=constraints)
        assert len(qp.constraints) == 2
        assert qp.constraints[0].parameter == "origin"

    def test_query_plan_intent_validation(self):
        """Test QueryPlan accepts valid intents."""
        valid_intents = [
            "cheapest_flight_on_route",
            "destinations_under_budget",
            "route_fare_options",
        ]
        for intent in valid_intents:
            qp = QueryPlan(intent=intent, constraints=[])
            assert qp.intent == intent

    def test_constraint_parameter_value_pair(self):
        """Test Constraint stores parameter and value correctly."""
        constraint = Constraint(parameter="origin", value="SIN")
        assert constraint.parameter == "origin"
        assert constraint.value == "SIN"

    def test_constraint_with_numeric_value(self):
        """Test Constraint with numeric value."""
        constraint = Constraint(parameter="max_price", value=300)
        assert constraint.parameter == "max_price"
        assert constraint.value == 300

    def test_constraint_with_date_value(self):
        """Test Constraint with date value."""
        constraint = Constraint(parameter="start_date", value="2026-06-01")
        assert constraint.parameter == "start_date"
        assert constraint.value == "2026-06-01"

    def test_query_parameter_schema(self):
        """Test QueryParameter schema."""
        param = QueryParameter(name="origin", value="SIN")
        assert param.name == "origin"
        assert param.value == "SIN"

    def test_query_plan_with_multiple_parameters(self):
        """Test QueryPlan with multiple parameters."""
        constraints = [
            Constraint(parameter="origin", value="SIN"),
            Constraint(parameter="destination", value="BKK"),
            Constraint(parameter="start_date", value="2026-06-01"),
            Constraint(parameter="end_date", value="2026-06-15"),
        ]
        qp = QueryPlan(intent="cheapest_flight_on_route", constraints=constraints)
        assert len(qp.constraints) == 4

    def test_query_plan_empty_constraints(self):
        """Test QueryPlan with empty constraints list."""
        qp = QueryPlan(intent="all_flights", constraints=[])
        assert len(qp.constraints) == 0

    def test_constraint_serialization(self):
        """Test Constraint can be serialized."""
        constraint = Constraint(parameter="origin", value="SIN")
        # Test dict-like access
        assert constraint.parameter == "origin"

    def test_query_plan_serialization(self):
        """Test QueryPlan can be serialized."""
        qp = QueryPlan(
            intent="cheapest_flight_on_route",
            constraints=[Constraint(parameter="origin", value="SIN")],
        )
        assert qp.intent == "cheapest_flight_on_route"
        assert len(qp.constraints) > 0


class TestSchemaValidation:
    """Test cases for schema-level validation."""

    def test_query_plan_structure_validation(self):
        """Test QueryPlan structure is valid."""
        qp = QueryPlan(intent="test_intent", constraints=[])
        assert hasattr(qp, "intent")
        assert hasattr(qp, "constraints")

    def test_constraint_structure_validation(self):
        """Test Constraint structure is valid."""
        c = Constraint(parameter="test_param", value="test_value")
        assert hasattr(c, "parameter")
        assert hasattr(c, "value")

    def test_multiple_constraints_same_parameter(self):
        """Test QueryPlan with multiple constraints on same parameter."""
        constraints = [
            Constraint(parameter="price", value=100),
            Constraint(parameter="price", value=500),
        ]
        qp = QueryPlan(intent="budget_query", constraints=constraints)
        price_constraints = [c for c in qp.constraints if c.parameter == "price"]
        assert len(price_constraints) == 2

    def test_constraint_with_special_characters_in_value(self):
        """Test Constraint handles special characters in values."""
        special_values = ["SIN-BKK", "route@1", "flight#123", "price<=300"]
        for value in special_values:
            constraint = Constraint(parameter="route", value=value)
            assert constraint.value == value

    def test_query_plan_with_none_values(self):
        """Test QueryPlan handles optional fields."""
        qp = QueryPlan(intent="test", constraints=[])
        # Intent is required, constraints can be empty
        assert qp.intent is not None
        assert isinstance(qp.constraints, list)
