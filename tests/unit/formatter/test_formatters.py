from unittest.mock import Mock

from formatter.telegram_formatter import TelegramFormatter
from formatter.web_formatter import WebFormatter
from models.pipeline import ResultSet
from models.common import SuccessResponse


def _make_flights_result_set(row_count=1):
    rows = []
    for i in range(row_count):
        rows.append({
            "f_airline_name": f"Airline {i+1}",
            "f_departure_date": "2026-04-30",
            "f_trip_type": "normal",
            "f_cabin_class": "Economy",
            "cheapest_fare": 100.50,
            "f_departure_airport_code": "SIN",
            "f_destination_airport_code": "BKK"
        })
    return ResultSet(request_id="req-1", type="flights", result_set=rows)


def test_telegram_formatter_empty_results():
    formatter = TelegramFormatter()
    rs = ResultSet(request_id="req-1", type="flights", result_set=[])
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert "couldn't find 'em" in result.data


def test_telegram_formatter_flights():
    formatter = TelegramFormatter()
    rs = _make_flights_result_set(row_count=2)
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert "I found 2 matching records" in result.data
    assert "Airline 1" in result.data
    assert "Airline 2" in result.data
    assert "SIN" in result.data
    assert "BKK" in result.data
    assert "100\\.5" in result.data


def test_telegram_formatter_other_type():
    formatter = TelegramFormatter()
    rs = ResultSet(request_id="req-1", type="other", result_set=[{"key": "val"}])
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert result.data == {"key": "val"}


def test_telegram_formatter_invalid_input():
    formatter = TelegramFormatter()
    # Mock an object that has request_id but is not a ResultSet
    rs = Mock()
    rs.request_id = "req-1"
    
    result = formatter.format_response(rs)
    assert isinstance(result, SuccessResponse)
    assert "circuits are a little tangled" in result.data


def test_web_formatter_empty_results():
    formatter = WebFormatter()
    rs = ResultSet(request_id="req-1", type="flights", result_set=[])
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert any("couldn't find 'em" in s for s in result.data)


def test_web_formatter_flights():
    formatter = WebFormatter()
    rs = _make_flights_result_set(row_count=2)
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert any("I found 2 matching records" in s for s in result.data)
    assert any("Airline 1" in s for s in result.data)
    assert any("Airline 2" in s for s in result.data)
    assert any("<b>SIN</b>" in s for s in result.data)
    assert any("<b>BKK</b>" in s for s in result.data)
    assert any("100.5" in s for s in result.data)


def test_web_formatter_other_type():
    formatter = WebFormatter()
    rs = ResultSet(request_id="req-1", type="other", result_set=[{"answer": "val"}])
    result = formatter.format_response(rs)
    
    assert isinstance(result, SuccessResponse)
    assert result.data == ["val"]


def test_web_formatter_invalid_input():
    formatter = WebFormatter()
    rs = Mock()
    rs.request_id = "req-1"
    
    result = formatter.format_response(rs)
    assert isinstance(result, SuccessResponse)
    assert any("circuits are a little tangled" in s for s in result.data)
