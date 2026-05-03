import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from configurations.app_config import AppConfig
from models.app_model import AppModel, ApiModel, AllowModel


@pytest.fixture
def app_config():
    """Fixture to create AppConfig instance"""
    return AppConfig()


def test_app_config_initialization(app_config):
    """Test AppConfig initializes with None config"""
    assert app_config._app_config is None


def test_app_config_getter_loads_config_on_first_access(app_config, tmp_path):
    """Test that config is loaded on first access"""
    # Create a mock config file
    config_content = """
[service]
host = "0.0.0.0"
port = 8000
reload = false
scheme = "http"
allow_origins = ["*"]
credentials = true
methods = ["*"]
headers = ["*"]
docs_url = "/docs"
redoc_url = ""
root_path = "/ontology"
"""
    config_file = tmp_path / "config.toml"
    config_file.write_text(config_content)
    
    with patch.object(app_config, '_load_config') as mock_load:
        mock_load.return_value = {
            'host': '0.0.0.0',
            'port': 8000,
            'reload': False,
            'scheme': 'http',
            'allow_origins': ['*'],
            'credentials': True,
            'methods': ['*'],
            'headers': ['*'],
            'docs_url': '/docs',
            'redoc_url': '',
            'root_path': '/ontology'
        }
        
        config = app_config.app_config
        assert config is not None
        assert isinstance(config, AppModel)
        mock_load.assert_called_once_with('service')


def test_app_config_getter_returns_cached_config(app_config):
    """Test that app_config getter returns cached value on subsequent calls"""
    mock_config = AppModel(
        host='0.0.0.0',
        port=8000,
        reload=False,
        scheme='http',
        api_endpoint=ApiModel(
            allow=AllowModel(
                origins=['*'],
                credentials=True,
                methods=['*'],
                headers=['*']
            ),
            redoc_url='',
            docs_url='/docs',
            root_path='/ontology'
        )
    )
    app_config._app_config = mock_config
    
    # Should return the same instance without calling _get_config
    config1 = app_config.app_config
    config2 = app_config.app_config
    
    assert config1 is config2
    assert config1 is mock_config


def test_app_config_setter(app_config):
    """Test app_config setter"""
    mock_config = AppModel(
        host='localhost',
        port=9000,
        reload=True,
        scheme='https',
        api_endpoint=ApiModel(
            allow=AllowModel(
                origins=['http://localhost'],
                credentials=False,
                methods=['GET', 'POST'],
                headers=['Content-Type']
            ),
            redoc_url='/redoc',
            docs_url='/docs',
            root_path='/api'
        )
    )
    
    app_config.app_config = mock_config
    assert app_config._app_config is mock_config
    assert app_config.app_config == mock_config


def test_app_config_get_config_with_valid_data(app_config):
    """Test _get_config with valid configuration data"""
    mock_load_result = {
        'host': '127.0.0.1',
        'port': 8080,
        'reload': True,
        'scheme': 'http',
        'allow_origins': ['http://localhost:3000'],
        'credentials': True,
        'methods': ['GET', 'POST', 'PUT'],
        'headers': ['Content-Type', 'Authorization'],
        'docs_url': '/api/docs',
        'redoc_url': '/api/redoc',
        'root_path': '/api/v1'
    }
    
    with patch.object(app_config, '_load_config', return_value=mock_load_result):
        app_config._get_config()
        
        assert app_config._app_config is not None
        assert app_config._app_config.host == '127.0.0.1'
        assert app_config._app_config.port == 8080
        assert app_config._app_config.reload is True
        assert app_config._app_config.scheme == 'http'
        assert app_config._app_config.api_endpoint.allow.origins == ['http://localhost:3000']
        assert app_config._app_config.api_endpoint.allow.credentials is True
        assert app_config._app_config.api_endpoint.docs_url == '/api/docs'
        assert app_config._app_config.api_endpoint.redoc_url == '/api/redoc'
        assert app_config._app_config.api_endpoint.root_path == '/api/v1'


def test_app_config_get_config_creates_nested_models(app_config):
    """Test that _get_config correctly creates nested models"""
    mock_load_result = {
        'host': '0.0.0.0',
        'port': 8000,
        'reload': False,
        'scheme': 'http',
        'allow_origins': ['*'],
        'credentials': True,
        'methods': ['*'],
        'headers': ['*'],
        'docs_url': '/docs',
        'redoc_url': '',
        'root_path': '/ontology'
    }
    
    with patch.object(app_config, '_load_config', return_value=mock_load_result):
        app_config._get_config()
        
        # Verify nested structure
        assert isinstance(app_config._app_config, AppModel)
        assert isinstance(app_config._app_config.api_endpoint, ApiModel)
        assert isinstance(app_config._app_config.api_endpoint.allow, AllowModel)
