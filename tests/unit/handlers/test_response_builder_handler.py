"""Unit tests for ResponseBuilderHandler."""

from unittest.mock import Mock

from handlers.response_formatter_handler import ResponseFormatterHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse, ResultSet, Row


def _result_set():
    return ResultSet(request_id="req-1", result_set=[Row(data={"fare": 100})])


def _question_response():
    return QuestionResponse(request_id="req-1", response="I found 1 matching record:\n1. {'fare': 100}")


def _make_handler(builder_return):
    builder = Mock()
    builder.build.return_value = builder_return
    return ResponseFormatterHandler(response_builder=builder), builder


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


# ── happy path ────────────────────────────────────────────────────────────


def test_response_builder_handler_builds_and_returns_response():
    rs = _result_set()
    expected = SuccessResponse(request_id="req-1", data=_question_response())
    handler, builder = _make_handler(builder_return=expected)

    request = NLQRequest(request_id="req-1", request_type="result", result_set=rs)
    result = handler.handle(request)

    builder.build.assert_called_once_with(rs)
    assert result is expected
    assert isinstance(result, SuccessResponse)


def test_response_builder_handler_passes_through_non_result_type():
    handler, builder = _make_handler(builder_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_executor")
    handler.handle(request)

    builder.build.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_response_builder_handler_returns_error_when_result_set_is_none():
    handler, builder = _make_handler(builder_return=None)

    request = NLQRequest(request_id="req-1", request_type="result", result_set=None)
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-1"
    builder.build.assert_not_called()


def test_response_builder_handler_propagates_error_from_builder():
    error = ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="build_failed", message="build error", component="response_builder"),
    )
    handler, _ = _make_handler(builder_return=error)

    request = NLQRequest(request_id="req-1", request_type="result", result_set=_result_set())
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "build_failed"
