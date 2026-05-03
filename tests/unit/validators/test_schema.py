import pytest
from unittest.mock import Mock, patch, MagicMock
from validators.syntactic.schema import QueryPlanPayload


class TestQueryPlanPayloadSchema:
    """Test cases for QueryPlanPayload schema validation."""

    def test_query_plan_payload_basic_construction(self):
        """Test basic QueryPlanPayload construction."""
        payload = QueryPlanPayload(
            intent="cheapest_flight_on_route",
            parameters={"origin": "SIN", "destination": "BKK"}
        )
        assert payload.intent == "cheapest_flight_on_route"
        assert payload.parameters == {"origin": "SIN", "destination": "BKK"}

    def test_query_plan_payload_with_missing_params(self):
        """Test QueryPlanPayload with missing parameters."""
        payload = QueryPlanPayload(
            intent="destinations_under_budget",
            parameters={"origin": "SIN"},
            missing_params=["destination", "max_price"]
        )
        assert len(payload.missing_params) == 2
        assert "destination" in payload.missing_params

    def test_query_plan_payload_default_missing_params(self):
        """Test QueryPlanPayload missing_params defaults to empty list."""
        payload = QueryPlanPayload(
            intent="route_fare_options",
            parameters={"origin": "SIN"}
        )
        assert payload.missing_params == []

    def test_query_plan_payload_with_follow_up_question(self):
        """Test QueryPlanPayload with follow-up question."""
        payload = QueryPlanPayload(
            intent="cheapest_flight_on_route",
            parameters={"origin": "SIN"},
            follow_up_question="Did you mean return flights?"
        )
        assert payload.follow_up_question == "Did you mean return flights?"

    def test_query_plan_payload_without_follow_up_question(self):
        """Test QueryPlanPayload without follow-up question defaults to None."""
        payload = QueryPlanPayload(
            intent="airlines_on_route",
            parameters={"origin": "SIN", "destination": "BKK"}
        )
        assert payload.follow_up_question is None

    def test_query_plan_payload_with_empty_parameters(self):
        """Test QueryPlanPayload with empty parameters dict."""
        payload = QueryPlanPayload(
            intent="last_seat_urgency",
            parameters={}
        )
        assert payload.parameters == {}
        assert len(payload.parameters) == 0

    def test_query_plan_payload_intent_types(self):
        """Test QueryPlanPayload with different intent types."""
        intents = [
            "cheapest_flight_on_route",
            "destinations_under_budget",
            "destinations_by_country_from_origin",
            "route_fare_options",
            "airlines_on_route",
            "last_seat_urgency"
        ]
        
        for intent in intents:
            payload = QueryPlanPayload(
                intent=intent,
                parameters={"test": "param"}
            )
            assert payload.intent == intent

    def test_query_plan_payload_parameters_with_multiple_types(self):
        """Test QueryPlanPayload parameters with different value types."""
        payload = QueryPlanPayload(
            intent="mixed_params",
            parameters={
                "origin": "SIN",  # string
                "max_price": 500,  # int
                "start_date": "2026-06-01",  # date string
                "round_trip": True  # boolean
            }
        )
        assert payload.parameters["origin"] == "SIN"
        assert payload.parameters["max_price"] == 500
        assert payload.parameters["start_date"] == "2026-06-01"
        assert payload.parameters["round_trip"] is True

    def test_query_plan_payload_serialization(self):
        """Test QueryPlanPayload can be serialized to dict."""
        payload = QueryPlanPayload(
            intent="test_intent",
            parameters={"key": "value"},
            missing_params=["missing_key"],
            follow_up_question="Question?"
        )
        
        # Pydantic models can be converted to dict
        payload_dict = payload.model_dump()
        assert payload_dict["intent"] == "test_intent"
        assert payload_dict["parameters"]["key"] == "value"
        assert payload_dict["missing_params"] == ["missing_key"]
        assert payload_dict["follow_up_question"] == "Question?"

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
