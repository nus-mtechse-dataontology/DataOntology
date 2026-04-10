"""Unit tests for SyntacticValidationHandler."""

from unittest.mock import Mock

from handlers.syntactic_validation_handler import SyntacticValidationHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QueryPlan


def _query_plan(request_id="req-1"):
    return QueryPlan(
        request_id=request_id,
        intent="cheapest_flight_on_route",
        parameters={"origin": "SIN"},
        confidence=0.9,
    )


def _make_handler(validator_return):
    validator = Mock()
    validator.validate.return_value = validator_return
    return SyntacticValidationHandler(syntactic_validator=validator), validator


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


def _error():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="malformed_json", message="bad json", component="syntactic_validator"),
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_syntactic_handler_validates_and_advances_type():
    plan = _query_plan()
    success = SuccessResponse(request_id="req-1", data=plan)
    handler, validator = _make_handler(validator_return=success)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", raw_response_text='{}', request_type="syntactic")
    handler.handle(request)

    validator.validate.assert_called_once_with(request)
    assert request.request_type == "semantics"
    assert request.query_plan == plan
    nxt.handle.assert_called_once_with(request)


def test_syntactic_handler_passes_through_non_syntactic_type():
    handler, validator = _make_handler(validator_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="llm")
    handler.handle(request)

    validator.validate.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_syntactic_handler_returns_error_when_validation_fails():
    handler, _ = _make_handler(validator_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="syntactic")
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "malformed_json"
    nxt.handle.assert_not_called()
