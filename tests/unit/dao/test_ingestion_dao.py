from unittest.mock import Mock, MagicMock, patch
import pytest
from sqlalchemy.exc import SQLAlchemyError
from dao.ingestion_dao import IngestionDAO
from models.ingestion_model import IngestionModel

@pytest.fixture
def mock_engine():
    return MagicMock()

@pytest.fixture
def ingestion_dao(mock_engine):
    return IngestionDAO(mock_engine)

@pytest.fixture
def mock_inspect():
    with patch("dao.ingestion_dao.inspect") as mock:
        mock_insp = MagicMock()
        # Mock the context manager _inspection_context()
        mock_insp._inspection_context.return_value.__enter__.return_value = MagicMock()
        mock_insp.get_table_names.return_value = ["test_table"]
        mock.return_value = mock_insp
        yield mock

def test_insert_many_success(ingestion_dao):
    with patch("dao.ingestion_dao.Session") as mock_session_cls:
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_session.exec.return_value.rowcount = 10
        
        ingestion_dao._db_table = Mock()
        result = ingestion_dao.insert_many([{"a": 1}])
        
        assert result["status"] == "success"
        assert result["records_inserted"] == 10
        mock_session.commit.assert_called_once()

def test_insert_many_failure(ingestion_dao):
    with patch("dao.ingestion_dao.Session") as mock_session_cls:
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_session.exec.side_effect = SQLAlchemyError("DB Error")
        
        ingestion_dao._db_table = Mock()
        result = ingestion_dao.insert_many([{"a": 1}])
        
        assert result["status"] == "error"
        assert result["records_inserted"] == 0

def test_upload_to_db(ingestion_dao, mock_inspect):
    payload = IngestionModel(table_name="test_table", truncate=True, data=[{"a": 1}])
    
    with patch.object(ingestion_dao, "_reflect_metadata") as mock_reflect:
        with patch.object(ingestion_dao, "truncate_table") as mock_truncate:
            with patch.object(ingestion_dao, "insert_many") as mock_insert:
                mock_insert.return_value = {"status": "success"}
                
                result = ingestion_dao.upload_to_db(payload)
                
                assert result["status"] == "success"
                mock_reflect.assert_called_once()
                mock_truncate.assert_called_once_with("test_table")
                mock_insert.assert_called_once_with([{"a": 1}])

def test_truncate_table_success(ingestion_dao, mock_inspect):
    with patch("dao.ingestion_dao.Session") as mock_session_cls, \
         patch("dao.ingestion_dao.delete") as mock_delete:
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_session.exec.return_value.rowcount = 5
        
        ingestion_dao._db_table = Mock()
        with patch.object(ingestion_dao, "_reflect_metadata"):
            result = ingestion_dao.truncate_table("test_table")
        
        assert result["status"] == "success"
        assert result["records_truncated"] == 5
        mock_session.commit.assert_called_once()

def test_truncate_table_failure(ingestion_dao, mock_inspect):
    with patch("dao.ingestion_dao.Session") as mock_session_cls, \
         patch("dao.ingestion_dao.delete") as mock_delete:
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_session.exec.side_effect = SQLAlchemyError("DB Error")
        
        ingestion_dao._db_table = Mock()
        with patch.object(ingestion_dao, "_reflect_metadata"):
            result = ingestion_dao.truncate_table("test_table")
        
        assert result["status"] == "error"
        assert result["records_truncated"] == 0

def test_get_table_data(ingestion_dao, mock_inspect):
    with patch("dao.ingestion_dao.Session") as mock_session_cls:
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_exec_result = MagicMock()
        mock_exec_result.mappings.return_value.all.return_value = [{"id": 1, "name": "test"}]
        mock_session.exec.return_value = mock_exec_result
        
        ingestion_dao._db_table = Mock()
        with patch.object(ingestion_dao, "_reflect_metadata"):
            result = ingestion_dao.get_table_data("test_table")
        
        assert result == [{"id": 1, "name": "test"}]

def test_get_schema_from_db(ingestion_dao, mock_inspect):
    mock_insp = mock_inspect.return_value
    mock_insp.get_table_names.return_value = ["table1", "dim_accounts"]
    mock_insp.get_columns.return_value = [
        {"name": "col1", "type": "TEXT", "nullable": True, "default": None, "autoincrement": False, "comment": None}
    ]
    
    result = ingestion_dao.get_schema_from_db()
    
    assert len(result) == 1
    assert result[0]["name"] == "table1"
    assert result[0]["cols"][0]["name"] == "col1"

def test_reflect_metadata(ingestion_dao, mock_inspect):
    ingestion_dao._table_name = "test_table"
    with patch("dao.ingestion_dao.MetaData") as mock_metadata_cls:
        mock_metadata = mock_metadata_cls.return_value
        mock_metadata.tables = {"test_table": "mock_table_obj"}
        
        ingestion_dao._reflect_metadata()
        
        assert ingestion_dao._db_table == "mock_table_obj"
        mock_metadata.reflect.assert_called_once()
