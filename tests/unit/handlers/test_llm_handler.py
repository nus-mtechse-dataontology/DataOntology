"""Unit tests for LLMHandler."""

from unittest.mock import Mock

from handlers.llm_handler import LLMHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse, NLQRequest


def _make_handler(llm_return):
    gateway = Mock()
    gateway.submit_prompt.return_value = llm_return
    return LLMHandler(llm_gateway=gateway), gateway


def _make_next(return_value=None):
    nxt = Mock()
    nxt.handle.return_value = return_value or SuccessResponse(request_id="req-1", data="ok")
    return nxt


def _error():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="llm_failed", message="LLM error", component="llm_gateway"),
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_llm_handler_calls_gateway_and_advances_type():
    raw = LLMRawResponse(raw_response_text='{"intent":"x"}')
    handler, gateway = _make_handler(llm_return=raw)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", system_message="sys", user_message="usr", request_type="llm")
    handler.handle(request)

    gateway.submit_prompt.assert_called_once_with(request)
    assert request.request_type == "syntactic"
    assert request.raw_response_text == '{"intent":"x"}'
    nxt.handle.assert_called_once_with(request)


def test_llm_handler_passes_through_non_llm_type():
    handler, gateway = _make_handler(llm_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="syntactic")
    handler.handle(request)

    gateway.submit_prompt.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_llm_handler_returns_error_when_gateway_fails():
    handler, _ = _make_handler(llm_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="llm")
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "llm_failed"
    nxt.handle.assert_not_called()


def test_llm_handler_short_circuits_on_error():
    """Downstream handler must not be called when LLM fails."""
    handler, _ = _make_handler(llm_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    handler.handle(NLQRequest(request_id="req-1", request_type="llm"))

    nxt.handle.assert_not_called()
