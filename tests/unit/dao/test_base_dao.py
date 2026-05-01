from unittest.mock import Mock, patch
import pytest
from sqlalchemy import Engine
from dao.base_dao import BaseDAO

# Concrete implementation of BaseDAO for testing
class MockDAO(BaseDAO):
    pass

def test_insert_many_success():
    mock_engine = Mock(spec=Engine)
    
    with patch("dao.base_dao.Session") as MockSession:
        session_instance = MockSession.return_value.__enter__.return_value
        
        dao = MockDAO(mock_engine)
        mock_objs = [Mock(), Mock()]
        
        result = dao.insert_many(mock_objs)
        
        session_instance.add_all.assert_called_once_with(mock_objs)
        session_instance.commit.assert_called_once()
        assert session_instance.refresh.call_count == 2
        assert result == mock_objs

def test_insert_many_error():
    mock_engine = Mock(spec=Engine)
    
    with patch("dao.base_dao.Session") as MockSession:
        session_instance = MockSession.return_value.__enter__.return_value
        session_instance.commit.side_effect = Exception("Commit failed")
        
        dao = MockDAO(mock_engine)
        
        with pytest.raises(Exception) as excinfo:
            dao.insert_many([Mock()])
        
        assert "Commit failed" in str(excinfo.value)
