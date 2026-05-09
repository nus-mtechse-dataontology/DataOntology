import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError
from ingestion.source.manual_source.manual_ingestion import ManualIngestion
from models.ingestion_model import IngestionModel
from session.db_session import DBSession

@pytest.fixture
def mock_db_session():
    session = MagicMock(spec=DBSession)
    session.engine = MagicMock()
    return session

@pytest.fixture
def mock_payload():
    return IngestionModel(
        table_name="test_table",
        truncate=False,
        data=[{"col1": "val1", "col2": 1}]
    )

@pytest.fixture
def manual_ingestion(mock_db_session, mock_payload):
    return ManualIngestion(mock_db_session, mock_payload)

def test_ingest_success(manual_ingestion, mock_db_session, mock_payload):
    with patch("ingestion.source.manual_source.manual_ingestion.MetaData") as mock_metadata_cls, \
         patch("ingestion.source.manual_source.manual_ingestion.Session") as mock_session_cls:
        
        mock_metadata = mock_metadata_cls.return_value
        mock_table = MagicMock()
        mock_metadata.tables = {mock_payload.table_name: mock_table}
        
        mock_session_instance = mock_session_cls.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session_instance.exec.return_value = mock_result
        
        result = manual_ingestion.ingest()
        
        assert result == {'status_code': 0, 'status': 'success', 'records_inserted': 1}
        mock_metadata.reflect.assert_called_once()
        mock_session_instance.exec.assert_called_once()
        mock_session_instance.commit.assert_called_once()

def test_get_table_metadata_failure(manual_ingestion, mock_payload):
    with patch("ingestion.source.manual_source.manual_ingestion.MetaData") as mock_metadata_cls:
        mock_metadata = mock_metadata_cls.return_value
        mock_metadata.tables = {} # Table not found
        
        with pytest.raises(KeyError):
            manual_ingestion._get_table_metadata()

def test_upload_to_db_success(manual_ingestion, mock_payload):
    manual_ingestion._db_table = MagicMock()
    with patch("ingestion.source.manual_source.manual_ingestion.Session") as mock_session_cls:
        mock_session_instance = mock_session_cls.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session_instance.exec.return_value = mock_result
        
        result = manual_ingestion._upload_to_db()
        
        assert result == {'status_code': 0, 'status': 'success', 'records_inserted': 1}
        mock_session_instance.commit.assert_called_once()

def test_upload_to_db_error(manual_ingestion):
    manual_ingestion._db_table = MagicMock()
    with patch("ingestion.source.manual_source.manual_ingestion.Session") as mock_session_cls:
        mock_session_instance = mock_session_cls.return_value.__enter__.return_value
        mock_session_instance.exec.side_effect = SQLAlchemyError("DB Error")
        
        result = manual_ingestion._upload_to_db()
        
        assert result == {'status_code': 1, 'status': 'error', 'records_inserted': 0}

def test_truncate_table_success(manual_ingestion, mock_payload):
    manual_ingestion._db_table = MagicMock()
    with patch("ingestion.source.manual_source.manual_ingestion.Session") as mock_session_cls, \
         patch("ingestion.source.manual_source.manual_ingestion.delete") as mock_delete:
        mock_session_instance = mock_session_cls.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_session_instance.exec.return_value = mock_result
        
        result = manual_ingestion._truncate_table()
        
        assert result == {'status_code': 0, 'status': 'success', 'records_truncated': 10}
        mock_session_instance.commit.assert_called_once()
        mock_delete.assert_called_once_with(manual_ingestion._db_table)

def test_truncate_table_error(manual_ingestion):
    manual_ingestion._db_table = MagicMock()
    with patch("ingestion.source.manual_source.manual_ingestion.Session") as mock_session_cls, \
         patch("ingestion.source.manual_source.manual_ingestion.delete") as mock_delete:
        mock_session_instance = mock_session_cls.return_value.__enter__.return_value
        mock_session_instance.exec.side_effect = SQLAlchemyError("DB Error")
        
        result = manual_ingestion._truncate_table()
        
        assert result == {'status_code': 1, 'status': 'error', 'records_truncated': 0}
