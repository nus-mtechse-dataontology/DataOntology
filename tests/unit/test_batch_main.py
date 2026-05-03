import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import tempfile
import yaml
import logging

from batch_main import IngestionAPI


@pytest.fixture
def ingestion_api():
    """Create IngestionAPI instance"""
    return IngestionAPI()


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory with dataset config"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create datasets directory
        datasets_dir = Path(tmpdir) / 'datasets'
        datasets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a sample YAML config
        config = {
            'modules': {
                'entry': {
                    'package': 'ingestion.entry.api_entry',
                    'class': 'ApiEntry'
                }
            },
            'source': {
                'type': 'api',
                'url': 'http://example.com/api'
            }
        }
        
        config_file = datasets_dir / 'test_ingestion.yml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        yield tmpdir


class TestIngestionAPI:
    """Test IngestionAPI CLI module"""
    
    def test_ingestion_api_initialization(self, ingestion_api):
        """Test IngestionAPI initializes correctly"""
        assert ingestion_api.app is not None
        assert ingestion_api._ingestion_name == ""
        assert ingestion_api._root == ""
        assert ingestion_api._config == {}
        assert ingestion_api._entry is None
        assert ingestion_api._session is None
    
    def test_ingestion_api_has_logger(self, ingestion_api):
        """Test IngestionAPI has logger configured"""
        assert ingestion_api._log is not None
        assert isinstance(ingestion_api._log, logging.Logger)
        assert ingestion_api._log.name == "ingestion"
    
    def test_ingestion_api_add_command(self, ingestion_api):
        """Test _add_command registers the main command"""
        # Verify the app has the command registered
        assert ingestion_api.app is not None
        assert callable(ingestion_api.app)
    
    @patch('batch_main.IngestionAPI._load_config')
    @patch('batch_main.IngestionAPI._get_session')
    @patch('batch_main.IngestionAPI._create_or_load_tables')
    @patch('batch_main.IngestionAPI._load_entry')
    @patch('batch_main.IngestionAPI._run')
    def test_main_with_valid_ingestion_type(
        self, mock_run, mock_load_entry, mock_create_tables, 
        mock_get_session, mock_load_config, ingestion_api
    ):
        """Test main method with valid ingestion type"""
        ingestion_api.main(ingestion_type="test_ingestion", project_path="/tmp/project")
        
        assert ingestion_api._ingestion_name == "test_ingestion"
        assert ingestion_api._root == "/tmp/project"
        mock_load_config.assert_called_once()
        mock_get_session.assert_called_once()
        mock_create_tables.assert_called_once()
        mock_load_entry.assert_called_once()
        mock_run.assert_called_once()
    
    def test_main_with_empty_ingestion_type_exits(self, ingestion_api):
        """Test main method exits when ingestion_type is empty"""
        with pytest.raises(SystemExit):
            ingestion_api.main(ingestion_type="", project_path="/tmp/project")
    
    @patch('batch_main.IngestionAPI._load_config')
    @patch('batch_main.IngestionAPI._get_session')
    @patch('batch_main.IngestionAPI._create_or_load_tables')
    @patch('batch_main.IngestionAPI._load_entry')
    @patch('batch_main.IngestionAPI._run')
    def test_main_sets_project_path_environment_variable(
        self, mock_run, mock_load_entry, mock_create_tables,
        mock_get_session, mock_load_config, ingestion_api
    ):
        """Test main sets PROJECT_PATH environment variable"""
        import os
        project_path = "/custom/project/path"
        
        ingestion_api.main(ingestion_type="test_ingestion", project_path=project_path)
        
        assert os.environ["PROJECT_PATH"] == project_path
    
    @patch('batch_main.IngestionAPI._load_config')
    def test_run_method_calls_entry_start(self, mock_load_config, ingestion_api):
        """Test _run method calls entry.start()"""
        mock_entry = MagicMock()
        ingestion_api._entry = mock_entry
        
        ingestion_api._run()
        
        mock_entry.start.assert_called_once()
    
    @patch('batch_main.im.import_module')
    @patch('batch_main.getattr')
    def test_load_entry_imports_and_instantiates_class(
        self, mock_getattr, mock_import, ingestion_api
    ):
        """Test _load_entry imports module and instantiates entry class"""
        mock_module = MagicMock()
        mock_entry_class = MagicMock()
        mock_import.return_value = mock_module
        mock_getattr.return_value = mock_entry_class
        
        ingestion_api._config = {
            'modules': {
                'entry': {
                    'package': 'test.package',
                    'class': 'TestEntry'
                }
            }
        }
        ingestion_api._session = MagicMock()
        
        ingestion_api._load_entry()
        
        mock_import.assert_called_once_with('test.package', 'test.package')
        mock_entry_class.assert_called_once_with(ingestion_api._config, ingestion_api._session)
        assert ingestion_api._entry is not None
    
    @patch('batch_main.SQLModel')
    def test_create_or_load_tables_creates_tables(self, mock_sqlmodel, ingestion_api):
        """Test _create_or_load_tables calls metadata.create_all"""
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_session.engine = mock_engine
        ingestion_api._session = mock_session
        
        ingestion_api._create_or_load_tables()
        
        mock_sqlmodel.metadata.create_all.assert_called_once_with(mock_engine)
    
    @patch('batch_main.DBSession')
    def test_get_session_creates_database_session(self, mock_db_session, ingestion_api):
        """Test _get_session creates DBSession instance"""
        mock_session_instance = MagicMock()
        mock_db_session.return_value = mock_session_instance
        
        ingestion_api._config = {'datasource': {}}
        ingestion_api._get_session()
        
        mock_db_session.assert_called_once_with(ingestion_api._config)
        assert ingestion_api._session == mock_session_instance
    
    @patch('builtins.open')
    @patch('batch_main.yaml.safe_load')
    def test_load_config_reads_yaml_file(self, mock_yaml_load, mock_open, ingestion_api):
        """Test _load_config reads and parses YAML config"""
        mock_config = {
            'modules': {'entry': {'package': 'test', 'class': 'Test'}},
            'source': {'type': 'api'}
        }
        mock_yaml_load.return_value = mock_config
        
        ingestion_api._root = "/project"
        ingestion_api._ingestion_name = "test_ingestion"
        ingestion_api._load_config()
        
        assert ingestion_api._config == mock_config
        mock_open.assert_called_once()
    
    @patch('builtins.open')
    @patch('batch_main.yaml.safe_load')
    def test_load_config_raises_on_invalid_yaml(self, mock_yaml_load, mock_open, ingestion_api):
        """Test _load_config raises on invalid YAML"""
        import yaml
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")
        
        ingestion_api._root = "/project"
        ingestion_api._ingestion_name = "test_ingestion"
        
        with pytest.raises(yaml.YAMLError):
            ingestion_api._load_config()
    
    def test_ingestion_api_app_is_typer_instance(self, ingestion_api):
        """Test that app is a Typer instance"""
        from typer import Typer
        assert isinstance(ingestion_api.app, Typer)
    
    @patch('batch_main.IngestionAPI._load_config')
    @patch('batch_main.IngestionAPI._get_session')
    @patch('batch_main.IngestionAPI._create_or_load_tables')
    @patch('batch_main.IngestionAPI._load_entry')
    @patch('batch_main.IngestionAPI._run')
    def test_main_called_with_default_empty_strings(
        self, mock_run, mock_load_entry, mock_create_tables,
        mock_get_session, mock_load_config, ingestion_api
    ):
        """Test main method with default empty string parameters"""
        with pytest.raises(SystemExit):
            ingestion_api.main()
