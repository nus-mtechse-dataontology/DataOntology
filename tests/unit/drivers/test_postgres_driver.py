from unittest.mock import Mock, patch, mock_open
import pytest
import os
from drivers.postgres_driver import PostgresDriver
from sqlalchemy import URL

def test_get_connection_success():
    config = {
        "datasource": {
            "database": {
                "drivername": "postgresql",
                "host": "localhost",
                "port": 5432,
                "name": "testdb",
                "options": {
                    "user": "user_vault",
                    "password": "pass_vault"
                }
            }
        }
    }
    
    # Mock environment variables
    with patch.dict(os.environ, {"PROJECT_PATH": "/tmp", "VAULT": "vault_dir"}), \
         patch("builtins.open", mock_open(read_data="secret_value")) as mocked_file:
        
        driver = PostgresDriver(config)
        connection = driver.get_connection()
        
        assert isinstance(connection, URL)
        assert connection.drivername == "postgresql"
        assert connection.username == "secret_value"
        assert connection.password == "secret_value"
        assert connection.host == "localhost"
        assert connection.port == 5432
        assert connection.database == "testdb"
        
        # Verify vault files were read
        assert mocked_file.call_count == 2

def test_get_connection_env_override():
    config = {
        "datasource": {
            "database": {
                "drivername": "postgresql",
                "host": "config_host",
                "port": 5432,
                "name": "config_db",
                "options": {
                    "user": "user_vault",
                    "password": "pass_vault"
                }
            }
        }
    }
    
    env_vars = {
        "PROJECT_PATH": "/tmp",
        "DRIVERNAME": "postgresql+psycopg2",
        "DB_HOST": "env_host",
        "DB_NAME": "env_db",
        "VAULT": "vault_dir"
    }
    
    with patch.dict(os.environ, env_vars), \
         patch("builtins.open", mock_open(read_data="secret_value")):
        
        driver = PostgresDriver(config)
        connection = driver.get_connection()
        
        assert connection.drivername == "postgresql+psycopg2"
        assert connection.host == "env_host"
        assert connection.database == "env_db"

def test_get_vault_file_not_found():
    config = {
        "datasource": {
            "database": {
                "drivername": "postgresql",
                "host": "localhost",
                "port": 5432,
                "name": "testdb",
                "options": {
                    "user": "missing_vault",
                    "password": "pass_vault"
                }
            }
        }
    }
    
    with patch("builtins.open", side_effect=FileNotFoundError):
        driver = PostgresDriver(config)
        with pytest.raises(FileNotFoundError):
            driver.get_connection()
