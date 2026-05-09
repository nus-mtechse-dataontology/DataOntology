import pytest
from graphdb.validator import validate

@pytest.fixture
def mock_semantics():
    return {
        "intents": {
            "cheapest_flight_on_route": {
                "required_params": ["origin", "destination"],
            },
            "country_info": {
                "required_params": ["country_name"],
            },
        },
        "param_schema": {
            "origin": {"pattern": "^[A-Z]{3}$"},
            "destination": {"pattern": "^[A-Z]{3}$"},
            "country_name": {"pattern": "^[a-zA-Z ]+$"},
        },
    }

def test_validate_success(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "parameters": {"origin": "SIN", "destination": "BKK"},
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is True
    assert msg == ""

def test_validate_missing_key(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is False
    assert "Missing key" in msg

def test_validate_confidence_out_of_range(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "parameters": {"origin": "SIN", "destination": "BKK"},
        "confidence": 1.1,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is False
    assert "Confidence out of range" in msg

def test_validate_unknown_intent(mock_semantics):
    query_plan = {
        "intent": "unknown_intent",
        "parameters": {"origin": "SIN", "destination": "BKK"},
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is False
    assert "Unknown intent" in msg

def test_validate_missing_required_param(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "parameters": {"origin": "SIN"},
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is False
    assert "Required param 'destination' missing" in msg

def test_validate_missing_param_flagged_by_llm(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "parameters": {"origin": "SIN"},
        "missing_params": ["destination"],
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is True
    assert msg == ""

def test_validate_param_pattern_mismatch(mock_semantics):
    query_plan = {
        "intent": "cheapest_flight_on_route",
        "parameters": {"origin": "SINGAPORE", "destination": "BKK"},
        "confidence": 0.95,
    }
    ok, msg = validate(query_plan, mock_semantics)
    assert ok is False
    assert "does not match pattern" in msg
