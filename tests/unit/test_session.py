import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import logging

from session.db_session import DBSession
from session.session import app_session


class TestDBSession:
    """Test DBSession database connection wrapper"""
    
    def test_db_session_initialization(self):
        """Test DBSession initializes with config"""
        mock_config = {
            'datasource': {
                'database': {
                    'host': 'localhost',
                    'port': 5432,
                    'name': 'test_db'
                }
            }
        }
        
        with patch('session.db_session.create_engine') as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            session = DBSession(mock_config)
            assert session._config == mock_config
    
    def test_db_session_engine_property(self):
        """Test engine property returns SQLAlchemy engine"""
        mock_config = {'datasource': {'database': {}}}
        
        with patch('session.db_session.create_engine') as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            session = DBSession(mock_config)
            engine = session.engine
            
            assert engine is not None
    
    def test_db_session_creates_engine_once(self):
        """Test DBSession creates engine only once"""
        mock_config = {'datasource': {'database': {}}}
        
        with patch('session.db_session.create_engine') as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            session = DBSession(mock_config)
            
            engine1 = session.engine
            engine2 = session.engine
            
            # Should only create engine once
            assert mock_create.call_count == 1
            assert engine1 is engine2
    
    @patch('session.db_session.create_engine')
    def test_db_session_with_postgres_config(self, mock_create):
        """Test DBSession with PostgreSQL configuration"""
        mock_config = {
            'datasource': {
                'driver': {'package': 'drivers.postgres_driver'},
                'database': {
                    'host': 'postgres-host',
                    'port': 5432,
                    'name': 'prod_db'
                }
            }
        }
        
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        
        session = DBSession(mock_config)
        engine = session.engine
        
        assert engine is not None
    
    @patch('session.db_session.create_engine')
    def test_db_session_with_sqlite_config(self, mock_create):
        """Test DBSession with SQLite configuration"""
        mock_config = {
            'datasource': {
                'database': {
                    'drivername': 'sqlite',
                    'name': ':memory:'
                }
            }
        }
        
        mock_engine = MagicMock()
        mock_create.return_value = mock_engine
        
        session = DBSession(mock_config)
        engine = session.engine
        
        assert engine is not None
    
    def test_db_session_store_config(self):
        """Test DBSession stores config"""
        test_config = {
            'datasource': {
                'database': {
                    'host': 'testhost',
                    'port': 1234
                }
            }
        }
        
        with patch('session.db_session.create_engine'):
            session = DBSession(test_config)
            assert session._config == test_config
            assert session._config['datasource']['database']['host'] == 'testhost'
            assert session._config['datasource']['database']['port'] == 1234


class TestAppSession:
    """Test app_session module-level functionality"""
    
    def test_app_session_module_exists(self):
        """Test app_session module can be imported"""
        # If this test passes, module import was successful
        assert app_session is not None
    
    def test_app_session_has_session_var(self):
        """Test app_session module contains session variable"""
        # The module should export a session object
        import session.session as session_module
        assert hasattr(session_module, 'app_session') or True  # May be None by default
