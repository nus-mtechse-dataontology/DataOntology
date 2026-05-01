from unittest.mock import Mock, patch
import pytest
from sqlalchemy import Engine
from dao.fact_flight_info_dao import FactFlightInfoDAO

def test_execute_raw_query_success():
    # Mock engine and session
    mock_engine = Mock(spec=Engine)
    
    # Mock the result mapping returning a list of dicts
    mock_result = Mock()
    mock_mappings = Mock()
    mock_mappings.all.return_value = [{"col1": "val1", "col2": "val2"}]
    mock_result.mappings.return_value = mock_mappings
    
    # We need to patch 'sqlmodel.Session' and 'sqlmodel.text'
    with patch("dao.fact_flight_info_dao.Session") as MockSession, \
         patch("dao.fact_flight_info_dao.text") as mock_text:
        
        # Setup the session instance mock
        session_instance = MockSession.return_value.__enter__.return_value
        session_instance.exec.return_value = mock_result
        
        dao = FactFlightInfoDAO(mock_engine)
        query = "SELECT * FROM flights"
        params = {"param1": "val1"}
        
        result = dao.execute_raw_query(query, params)
        
        # Verify calls
        mock_text.assert_called_once_with(query)
        session_instance.exec.assert_called_once_with(mock_text.return_value, params=params)
        assert result == [{"col1": "val1", "col2": "val2"}]

def test_execute_raw_query_error():
    mock_engine = Mock(spec=Engine)
    
    with patch("dao.fact_flight_info_dao.Session") as MockSession:
        session_instance = MockSession.return_value.__enter__.return_value
        session_instance.exec.side_effect = Exception("DB Error")
        
        dao = FactFlightInfoDAO(mock_engine)
        
        with pytest.raises(Exception) as excinfo:
            dao.execute_raw_query("SELECT 1")
        
        assert "DB Error" in str(excinfo.value)
