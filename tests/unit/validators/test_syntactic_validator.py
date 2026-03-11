"""Tests for syntactic validator."""

from validators.syntactic.syntactic_validator import SyntacticValidator
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse


def _make_raw(request_id: str, text: str) -> LLMRawResponse:
    return LLMRawResponse(request_id=request_id, raw_response_text=text)


def test_valid_json_returns_success():
    validator = SyntacticValidator()
    raw = _make_raw(
        "req-1",
        """
        {
            "intent": "cheapest_return_flight",
            "parameters": {"origin": "SIN", "destination": "BKK"},
            "missing_params": [],
            "follow_up_question": null,
            "confidence": 0.95
        }
        """,
    )
    result = validator.validate(raw)
    assert isinstance(result, SuccessResponse)
    assert result.data.intent == "cheapest_return_flight"
    assert result.data.confidence == 0.95
    assert result.data.request_id == "req-1"


def test_markdown_fenced_json_returns_success():
    validator = SyntacticValidator()
    raw = _make_raw(
        "req-fence",
        '```json\n{"intent":"cheapest_return_flight","parameters":{},'
        '"missing_params":[],"follow_up_question":null,"confidence":0.8}\n```',
    )
    result = validator.validate(raw)
    assert isinstance(result, SuccessResponse)
    assert result.data.intent == "cheapest_return_flight"


def test_malformed_json_returns_error():
    validator = SyntacticValidator()
    raw = _make_raw("req-2", "{ invalid json }")
    result = validator.validate(raw)
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "malformed_json"


def test_missing_required_fields_returns_schema_error():
    validator = SyntacticValidator()
    raw = _make_raw("req-3", '{"parameters": {}}')
    result = validator.validate(raw)
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "schema_validation_error"


def test_confidence_above_1_returns_error():
    validator = SyntacticValidator()
    raw = _make_raw(
        "req-4",
        """
        {
            "intent": "cheapest_return_flight",
            "parameters": {},
            "missing_params": [],
            "follow_up_question": null,
            "confidence": 1.5
        }
        """,
    )
    result = validator.validate(raw)
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_confidence"


def test_confidence_below_0_returns_error():
    validator = SyntacticValidator()
    raw = _make_raw(
        "req-5",
        """
        {
            "intent": "cheapest_return_flight",
            "parameters": {},
            "missing_params": [],
            "follow_up_question": null,
            "confidence": -0.1
        }
        """,
    )
    result = validator.validate(raw)
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_confidence"


def test_empty_string_returns_malformed_json():
    validator = SyntacticValidator()
    raw = _make_raw("req-6", "")
    result = validator.validate(raw)
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "malformed_json"