"""Tests for semantic validator."""

from validators.semantic.semantic_validator import SemanticValidator
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import QueryPlan


def _make_plan(
    request_id="req-1",
    intent="cheapest_return_flight",
    parameters=None,
    missing_params=None,
    confidence=0.9,
):
    return QueryPlan(
        request_id=request_id,
        intent=intent,
        parameters=parameters or {},
        missing_params=missing_params or [],
        follow_up_question=None,
        confidence=confidence,
    )


def _make_semantic_model():
    """Minimal semantic model matching the actual structure in semantic_layer.json."""
    return {
        "intents": {
            "cheapest_return_flight": {
                "description": "Find cheapest return flight",
                "required_params": ["origin", "destination", "start_date", "end_date"],
                "sql_template": "SELECT ... LIMIT :limit",
            },
            "destinations_under_budget_return": {
                "description": "List destinations under budget",
                "required_params": ["origin", "max_price", "start_date", "end_date"],
                "sql_template": "SELECT ... LIMIT :limit",
            },
        },
        "param_schema": {
            "origin": {
                "type": "string",
                "format": "iata_airport_code",
                "pattern": "^[A-Z]{3}$",
            },
            "destination": {
                "type": "string",
                "format": "iata_airport_code",
                "pattern": "^[A-Z]{3}$",
            },
            "start_date": {
                "type": "string",
                "format": "date",
                "pattern": r"^\d{4}-\d{2}-\d{2}$",
            },
            "end_date": {
                "type": "string",
                "format": "date",
                "pattern": r"^\d{4}-\d{2}-\d{2}$",
            },
            "max_price": {
                "type": "number",
                "minimum": 0,
            },
        },
    }


def test_valid_plan_returns_success():
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        }
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, SuccessResponse)
    assert result.data.intent == "cheapest_return_flight"


def test_invalid_intent_returns_error():
    validator = SemanticValidator()
    plan = _make_plan(intent="nonexistent_intent")
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_intent"


def test_missing_required_params_returns_error():
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={"origin": "SIN"}  # missing destination, start_date, end_date
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "missing_required_params"
    assert "destination" in result.error.details["missing_params"]


def test_llm_flagged_missing_params_returns_error():
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        },
        missing_params=["end_date"],
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "llm_flagged_missing_params"


def test_invalid_iata_code_format_returns_error():
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={
            "origin": "singapore",  # not IATA format
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        },
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_param_format"


def test_invalid_date_format_returns_error():
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "September 2019",  # not ISO date
            "end_date": "2019-09-30",
        },
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_param_format"


def test_extra_params_are_allowed():
    """Extra params beyond required_params should not cause errors."""
    validator = SemanticValidator()
    plan = _make_plan(
        parameters={
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
            "limit": 5,
        },
    )
    result = validator.validate(plan, _make_semantic_model())
    assert isinstance(result, SuccessResponse)


def test_empty_semantic_model_intents_returns_error():
    validator = SemanticValidator()
    plan = _make_plan()
    result = validator.validate(plan, {"intents": {}})
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_intent"