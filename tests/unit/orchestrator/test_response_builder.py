from handlers.response_formatter_handler import ResponseFormatterHandler
from formatter.web_formatter import WebFormatter
from formatter.telegram_formatter import TelegramFormatter
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, ResultSet, Row

def test_response_formatter_handler_success():
    formatters = {"web": WebFormatter, "telegram": TelegramFormatter}
    handler = ResponseFormatterHandler(formatters)
    
    request = NLQRequest(
        request_id="req-123",
        question="Cheapest flight",
        source="web",
        request_type="result",
            result_set=ResultSet(
                request_id="req-123",
                type="flights",
                result_set=[{
                "f_airline_name": "AirAsia",
                "f_departure_date": "2024-01-01",
                "f_trip_type": "normal",
                "f_cabin_class": "Economy",
                "cheapest_fare": 100,
                "f_departure_airport_code": "SIN",
                "f_destination_airport_code": "BKK"
            }]
        )
    )
    
    result = handler.handle(request)
    
    assert isinstance(result, SuccessResponse)
    assert result.request_id == "req-123"
    assert "I found 1 matching record" in result.data[0]

def test_response_formatter_handler_no_results():
    formatters = {"web": WebFormatter}
    handler = ResponseFormatterHandler(formatters)
    
    request = NLQRequest(
        request_id="req-123",
        question="Cheapest flight",
        source="web",
        request_type="result",
        result_set=ResultSet(
            request_id="req-123",
            type_="flights",
            result_set=[]
        )
    )
    
    result = handler.handle(request)
    
    assert isinstance(result, SuccessResponse)
    assert "couldn't find 'em" in result.data[0]

def test_response_formatter_handler_error_result_set_none():
    formatters = {"web": WebFormatter}
    handler = ResponseFormatterHandler(formatters)
    
    request = NLQRequest(
        request_id="req-123",
        question="Cheapest flight",
        source="web",
        request_type="result",
        result_set=None
    )
    
    result = handler.handle(request)
    
    assert isinstance(result, ErrorResponse)
    assert "ResultSet is None" in result.error.message

def test_response_formatter_handler_error_unknown_source():
    formatters = {"web": WebFormatter}
    handler = ResponseFormatterHandler(formatters)
    
    request = NLQRequest(
        request_id="req-123",
        question="Cheapest flight",
        source="unknown",
        request_type="result",
        result_set=ResultSet(request_id="req-123", type_="flights", result_set=[])
    )
    
    result = handler.handle(request)
    
    assert isinstance(result, ErrorResponse)
    assert "Unknown source" in result.error.message

def test_response_formatter_handler_ignores_non_result_request():
    # Since it's an AbstractHandler, we can mock the next handler
    class MockHandler:
        def handle(self, request):
            return "next_handler_called"
            
    formatters = {"web": WebFormatter}
    handler = ResponseFormatterHandler(formatters)
    handler.set_next(MockHandler())
    
    request = NLQRequest(
        request_id="req-123",
        question="Cheapest flight",
        source="web",
        request_type="general", # Not "result"
        result_set=None
    )
    
    result = handler.handle(request)
    assert result == "next_handler_called"
