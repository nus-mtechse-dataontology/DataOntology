from unittest.mock import Mock, patch
import pytest
from sqlalchemy import Engine
from dao.flight_search_dao import FlightSearchDAO
from entities.airport import Airport

def test_get_all_airports_success():
    mock_engine = Mock(spec=Engine)
    
    mock_airports = [Airport(id=1, name="SIN"), Airport(id=2, name="BKK")]
    
    with patch("dao.flight_search_dao.Session") as MockSession, \
         patch("dao.flight_search_dao.select") as mock_select:
        
        session_instance = MockSession.return_value.__enter__.return_value
        session_instance.exec.return_value = mock_airports
        
        dao = FlightSearchDAO(mock_engine)
        result = dao.get_all_airports()
        
        mock_select.assert_called_once_with(Airport)
        session_instance.exec.assert_called_once_with(mock_select.return_value)
        assert result == mock_airports

def test_get_all_airports_empty():
    mock_engine = Mock(spec=Engine)
    
    with patch("dao.flight_search_dao.Session") as MockSession, \
         patch("dao.flight_search_dao.select") as mock_select:
        
        session_instance = MockSession.return_value.__enter__.return_value
        session_instance.exec.return_value = []
        
        dao = FlightSearchDAO(mock_engine)
        result = dao.get_all_airports()
        
        assert result == []
