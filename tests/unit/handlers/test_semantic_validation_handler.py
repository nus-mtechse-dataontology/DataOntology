"""Unit tests for SemanticsValidationHandler."""

from unittest.mock import Mock, patch

from handlers.semantic_validation_handler import SemanticsValidationHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QueryPlan


SEMANTICS = {"intents": {"cheapest_flight_on_route": {}}, "param_schema": {}}


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
    handler = SemanticsValidationHandler(semantics_validation=validator)
    handler._semantics = SEMANTICS
    return handler, validator


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


def _error():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="invalid_intent", message="unknown intent", component="semantic_validator"),
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_semantics_handler_validates_and_advances_type():
    plan = _query_plan()
    success = SuccessResponse(request_id="req-1", data=plan)
    handler, validator = _make_handler(validator_return=success)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="semantics", query_plan=plan)
    with patch.object(handler, "_load_semantics"):
        handler.handle(request)

    validator.validate.assert_called_once_with(plan, SEMANTICS)
    assert request.request_type == "sql_compile"
    nxt.handle.assert_called_once_with(request)


def test_semantics_handler_passes_through_non_semantics_type():
    handler, validator = _make_handler(validator_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="syntactic")
    handler.handle(request)

    validator.validate.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_semantics_handler_returns_error_when_query_plan_is_none():
    handler, validator = _make_handler(validator_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="semantics", query_plan=None)
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    validator.validate.assert_not_called()
    nxt.handle.assert_not_called()


def test_semantics_handler_returns_error_when_validation_fails():
    plan = _query_plan()
    handler, _ = _make_handler(validator_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="semantics", query_plan=plan)
    with patch.object(handler, "_load_semantics"):
        result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_intent"
    nxt.handle.assert_not_called()
