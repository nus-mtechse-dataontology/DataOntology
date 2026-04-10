"""Unit tests for RequestHandler."""

from unittest.mock import Mock

from handlers.request_handler import RequestHandler
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest


def _make_next(return_value=None):
    nxt = Mock()
    nxt.handle.return_value = return_value or SuccessResponse(
        request_id="req-1", data="ok"
    )
    return nxt


# ── happy path ────────────────────────────────────────────────────────────


def test_request_handler_processes_request_type():
    handler = RequestHandler()
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="cheapest flight?", request_type="request")
    handler.handle(request)

    assert request.request_type == "prompt"


def test_request_handler_assigns_request_id():
    handler = RequestHandler()
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="unknown", question="q", request_type="request")
    handler.handle(request)

    assert request.request_id != "unknown"
    assert len(request.request_id) == 36  # UUID4 format


def test_request_handler_delegates_to_next_handler():
    handler = RequestHandler()
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="q", request_type="request")
    handler.handle(request)

    nxt.handle.assert_called_once_with(request)


def test_request_handler_passes_through_non_request_type():
    """If request_type is not 'request', handler should pass to next without modifying."""
    handler = RequestHandler()
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="q", request_type="prompt")
    handler.handle(request)

    assert request.request_type == "prompt"
    nxt.handle.assert_called_once_with(request)


def test_request_handler_returns_next_handler_result():
    handler = RequestHandler()
    expected = SuccessResponse(request_id="req-1", data="result")
    nxt = _make_next(return_value=expected)
    handler.set_next(nxt)

    result = handler.handle(NLQRequest(request_id="req-1", question="q", request_type="request"))

    assert result is expected
