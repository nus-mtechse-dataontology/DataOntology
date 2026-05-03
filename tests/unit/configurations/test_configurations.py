import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from configurations.admin_config import AdminConfig
from configurations.app_config import AppConfig
from configurations.logger_config import LoggerConfig


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory with a valid config.toml for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_content = """
[service]
title = "Test Data Ontology"
root_path = "/ontology"
port = 8000
host = "0.0.0.0"
credentials = true
allow_origins = ["*"]
methods = ["*"]
headers = ["*"]
docs_url = "/docs"
redoc_url = "/redoc"
reload = false
scheme = "http"

[admin]
admin_host = "127.0.0.1"
admin_port = 8080
context_path = "/admin/instances"
scheme = "http"

[logger]
version = 1
disable_existing_loggers = false

[logger.handlers.console]
class = "logging.StreamHandler"
level = "INFO"
formatter = "default"
stream = "ext://sys.stdout"

[logger.formatters.default]
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""
        config_dir = Path(tmpdir) / "resources"
        config_dir.mkdir()
        with open(config_dir / "config.toml", "w") as f:
            f.write(config_content)
        yield config_dir.parent


class TestAppConfig:
    def test_app_config_initialization(self, temp_config_dir):
        """Test AppConfig initializes successfully."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AppConfig()
            assert config.app_config is not None

    def test_app_config_properties(self, temp_config_dir):
        """Test AppConfig returns correct properties."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AppConfig()
            assert config.app_config.port == 8000
            assert config.app_config.host == "0.0.0.0"
            assert config.app_config.reload is False

    def test_app_config_setter(self):
        """Test AppConfig setter works correctly."""
        config = AppConfig()
        mock_app_model = MagicMock()
        config.app_config = mock_app_model
        assert config.app_config == mock_app_model

    def test_app_config_api_endpoint(self, temp_config_dir):
        """Test AppConfig API endpoint configuration."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AppConfig()
            api_endpoint = config.app_config.api_endpoint
            assert api_endpoint is not None
            assert api_endpoint.docs_url == "/docs"
            assert "*" in api_endpoint.allow.origins


class TestAdminConfig:
    def test_admin_config_initialization(self, temp_config_dir):
        """Test AdminConfig initializes successfully."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AdminConfig()
            assert config.admin_config is not None

    def test_admin_config_properties(self, temp_config_dir):
        """Test AdminConfig returns correct properties."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AdminConfig()
            assert config.admin_config.admin_host == "127.0.0.1"
            assert config.admin_config.admin_port == 8080
            assert config.admin_config.context_path == "/admin/instances"

    def test_admin_config_setter(self):
        """Test AdminConfig setter works correctly."""
        config = AdminConfig()
        mock_admin_model = MagicMock()
        config.admin_config = mock_admin_model
        assert config.admin_config == mock_admin_model


class TestLoggerConfig:
    def test_logger_config_initialization(self, temp_config_dir):
        """Test LoggerConfig initializes successfully."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = LoggerConfig()
            assert config is not None

    def test_logger_config_loads_config(self, temp_config_dir):
        """Test LoggerConfig loads configuration."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = LoggerConfig()
            # Verify logger config was created (it uses logging.config.dictConfig)
            assert isinstance(config, LoggerConfig)


class TestConfigLoadingErrors:
    def test_config_file_not_found_raises_error(self):
        """Test that missing config file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"PROJECT_PATH": str(tmpdir)}):
                config = AppConfig()
                with pytest.raises(FileNotFoundError):
                    _ = config.app_config

    def test_config_caching(self, temp_config_dir):
        """Test that config is cached after first access."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AppConfig()
            first_access = config.app_config
            second_access = config.app_config
            # Same object reference (cached)
            assert first_access is second_access


class TestProjectPathResolution:
    def test_default_project_path_when_env_not_set(self):
        """Test that default project path is resolved correctly when env not set."""
        with patch.dict("os.environ", {}, clear=False):
            if "PROJECT_PATH" in os.environ:
                del os.environ["PROJECT_PATH"]
            config = AppConfig()
            # Should resolve to parent of src/configurations
            assert config._root.name == "DataOntology"

    def test_project_path_from_env_variable(self, temp_config_dir):
        """Test that PROJECT_PATH env variable is used when set."""
        with patch.dict("os.environ", {"PROJECT_PATH": str(temp_config_dir)}):
            config = AppConfig()
            assert str(temp_config_dir) in str(config._root)


import os
