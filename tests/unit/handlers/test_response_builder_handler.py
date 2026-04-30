"""Unit tests for ResponseFormatterHandler."""

from unittest.mock import Mock
from typing import Dict, Type

from handlers.response_formatter_handler import ResponseFormatterHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, ResultSet

def _result_set():
    return ResultSet(request_id="req-1", result_set=[{"fare": 100}])


def _make_handler(formatters: Dict[str, Type] = None):
    if formatters is None:
        mock_formatter = Mock()
        mock_formatter.format_response.return_value = SuccessResponse(request_id="req-1", data="formatted")
        formatters = {"web": type("MockFormatter", (), {"format_response": Mock(return_value=SuccessResponse(request_id="req-1", data="formatted"))})()}
        # Actually, ResponseFormatterHandler expects a dict of CLASSES, not instances.
        # Let's fix this.
        class MockFormatter:
            def format_response(self, response):
                return SuccessResponse(request_id="req-1", data="formatted")
        formatters = {"web": MockFormatter}

    return ResponseFormatterHandler(formatters)


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


def test_response_formatter_handler_builds_and_returns_response():
    class MockFormatter:
        def format_response(self, response):
            return SuccessResponse(request_id="req-1", data="formatted")
    
    handler = ResponseFormatterHandler({"web": MockFormatter})
    
    request = NLQRequest(
        request_id="req-1", 
        request_type="result", 
        result_set=_result_set(),
        source="web"
    )
    result = handler.handle(request)

    assert result.data == "formatted"
    assert isinstance(result, SuccessResponse)


def test_response_formatter_handler_passes_through_non_result_type():
    handler = ResponseFormatterHandler({"web": Mock})
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_executor")
    handler.handle(request)

    nxt.handle.assert_called_once_with(request)


def test_response_formatter_handler_returns_error_when_result_set_is_none():
    handler = ResponseFormatterHandler({"web": Mock})

    request = NLQRequest(request_id="req-1", request_type="result", result_set=None, source="web")
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-1"


def test_response_formatter_handler_returns_error_when_source_unknown():
    handler = ResponseFormatterHandler({"web": Mock})

    request = NLQRequest(request_id="req-1", request_type="result", result_set=_result_set(), source="unknown")
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert "Unknown source" in result.error.message
