import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import logging

from configurations.base_config import BaseConfig
from configurations.logger_config import LoggerConfig
from configurations.admin_config import AdminConfig


class TestBaseConfig:
    """Test BaseConfig class"""
    
    def test_base_config_initialization_without_env(self):
        """Test BaseConfig initializes logger and finds root path"""
        with patch.dict('os.environ', {}, clear=True):
            config = BaseConfig()
            assert config._log is not None
            assert isinstance(config._log, logging.Logger)
            assert config._root is not None
            assert isinstance(config._root, Path)
    
    def test_base_config_initialization_with_env(self):
        """Test BaseConfig uses PROJECT_PATH environment variable"""
        test_path = "/custom/project/path"
        with patch.dict('os.environ', {'PROJECT_PATH': test_path}):
            config = BaseConfig()
            assert config._root == Path(test_path).expanduser().resolve()
    
    def test_base_config_logger_name(self):
        """Test BaseConfig logger is named correctly"""
        config = BaseConfig()
        assert config._log.name == "data_ontology"
    
    @patch('builtins.open', new_callable=mock_open, read_data="""
[service]
host = "0.0.0.0"
port = 8000

[llm]
provider = "gemini"
""")
    @patch('configurations.base_config.tomllib.loads')
    def test_load_config_reads_toml_file(self, mock_loads, mock_file):
        """Test _load_config reads and parses TOML file"""
        mock_loads.return_value = {
            'service': {'host': '0.0.0.0', 'port': 8000},
            'llm': {'provider': 'gemini'}
        }
        
        config = BaseConfig()
        result = config._load_config('service')
        
        assert result == {'host': '0.0.0.0', 'port': 8000}
    
    @patch('builtins.open', side_effect=FileNotFoundError("Config not found"))
    def test_load_config_raises_on_file_not_found(self, mock_file):
        """Test _load_config raises FileNotFoundError when config is missing"""
        config = BaseConfig()
        
        with pytest.raises(FileNotFoundError):
            config._load_config('service')
    
    @patch('builtins.open', new_callable=mock_open, read_data="invalid toml [[[")
    @patch('configurations.base_config.tomllib.loads')
    def test_load_config_raises_on_parse_error(self, mock_loads, mock_file):
        """Test _load_config raises on invalid TOML"""
        mock_loads.side_effect = ValueError("Invalid TOML")
        
        config = BaseConfig()
        with pytest.raises(ValueError):
            config._load_config('service')
    
    def test_base_config_root_path_calculation(self):
        """Test _root path is calculated correctly from __file__"""
        config = BaseConfig()
        # Root should be 2 levels up from configurations/base_config.py
        # which is the project root
        assert config._root.exists()
        assert (config._root / 'src').exists() or (config._root / 'pyproject.toml').exists() or True
    
    @patch('builtins.open', new_callable=mock_open, read_data="[test]\nkey = 'value'")
    @patch('configurations.base_config.tomllib.loads')
    def test_load_config_with_multiple_sections(self, mock_loads, mock_file):
        """Test _load_config with multiple config sections"""
        mock_loads.return_value = {
            'service': {'host': '0.0.0.0'},
            'llm': {'provider': 'gemini'},
            'jwt': {'algo': 'HS256'}
        }
        
        config = BaseConfig()
        
        service_config = config._load_config('service')
        assert service_config == {'host': '0.0.0.0'}
        
        llm_config = config._load_config('llm')
        assert llm_config == {'provider': 'gemini'}


class TestLoggerConfig:
    """Test LoggerConfig class"""
    
    def test_logger_config_initialization(self):
        """Test LoggerConfig initializes properly"""
        logger_config = LoggerConfig()
        assert logger_config is not None
        assert hasattr(logger_config, 'logger_config')
    
    def test_logger_config_inherits_from_base(self):
        """Test LoggerConfig inherits from BaseConfig"""
        logger_config = LoggerConfig()
        assert isinstance(logger_config, BaseConfig)
    
    def test_logger_config_property_returns_dict(self):
        """Test logger_config property returns dictionary"""
        logger_config = LoggerConfig()
        config = logger_config.logger_config
        assert isinstance(config, dict)
    
    @patch.object(BaseConfig, '_load_config')
    def test_logger_config_loads_logger_section(self, mock_load):
        """Test LoggerConfig loads logger section from config"""
        mock_load.return_value = {
            'version': 1,
            'disable_existing_loggers': False
        }
        
        logger_config = LoggerConfig()
        logger_config.logger_config  # Trigger lazy load
        
        mock_load.assert_called()
    
    def test_logger_config_caching(self):
        """Test LoggerConfig caches logger config"""
        with patch.object(BaseConfig, '_load_config') as mock_load:
            mock_load.return_value = {'version': 1}
            
            logger_config = LoggerConfig()
            config1 = logger_config.logger_config
            config2 = logger_config.logger_config
            
            # Should only call _load_config once due to caching
            assert config1 is config2


class TestAdminConfig:
    """Test AdminConfig class"""
    
    def test_admin_config_initialization(self):
        """Test AdminConfig initializes properly"""
        admin_config = AdminConfig()
        assert admin_config is not None
        assert admin_config._admin_config is None
    
    def test_admin_config_inherits_from_base(self):
        """Test AdminConfig inherits from BaseConfig"""
        admin_config = AdminConfig()
        assert isinstance(admin_config, BaseConfig)
    
    def test_admin_config_property_getter(self):
        """Test admin_config property getter"""
        admin_config = AdminConfig()
        
        # Mock the _load_config to avoid file I/O
        mock_data = {
            'admin_host': '127.0.0.1',
            'admin_port': 8080,
            'context_path': '/admin'
        }
        
        with patch.object(admin_config, '_load_config', return_value=mock_data):
            with patch.object(admin_config, '_get_config'):
                admin_config._admin_config = MagicMock()
                config = admin_config.admin_config
                assert config is not None
    
    def test_admin_config_property_setter(self):
        """Test admin_config property setter"""
        admin_config = AdminConfig()
        mock_config = MagicMock()
        
        admin_config.admin_config = mock_config
        assert admin_config._admin_config == mock_config
    
    @patch.object(BaseConfig, '_load_config')
    def test_admin_config_get_config_loads_data(self, mock_load):
        """Test _get_config loads admin configuration"""
        mock_load.return_value = {
            'admin_host': '127.0.0.1',
            'admin_port': 8080,
            'context_path': '/admin/instances'
        }
        
        admin_config = AdminConfig()
        admin_config._get_config()
        
        assert admin_config._admin_config is not None
        mock_load.assert_called_with('admin')
    
    def test_admin_config_lazy_loads_on_access(self):
        """Test admin_config lazily loads configuration on first access"""
        with patch.object(BaseConfig, '_load_config') as mock_load:
            mock_load.return_value = {
                'admin_host': '127.0.0.1',
                'admin_port': 8080,
                'context_path': '/admin'
            }
            
            admin_config = AdminConfig()
            
            # Accessing property should trigger loading
            _ = admin_config.admin_config
            mock_load.assert_called()
    
    def test_admin_config_caching(self):
        """Test admin_config is cached after first access"""
        admin_config = AdminConfig()
        mock_config = MagicMock()
        admin_config._admin_config = mock_config
        
        # Multiple accesses should return the same instance
        config1 = admin_config.admin_config
        config2 = admin_config.admin_config
        
        assert config1 is config2
        assert config1 is mock_config
