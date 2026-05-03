import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import logging

from session.db_session import DBSession
from session.session import Session


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


class TestSessionAbstract:
    """Test Session abstract base class"""
    
    def test_session_is_abstract(self):
        """Test Session is an abstract base class"""
        from abc import ABC
        assert issubclass(Session, ABC)
    
    def test_session_initialization_creates_logger(self):
        """Test Session initializes with logger"""
        # Cannot instantiate abstract class, so test through a concrete implementation
        class ConcreteSession(Session):
            def create_session(self):
                pass
        
        session = ConcreteSession()
        assert session._log is not None
        assert isinstance(session._log, logging.Logger)
    
    def test_session_has_create_session_method(self):
        """Test Session defines create_session abstract method"""
        assert hasattr(Session, 'create_session')
    
    def test_concrete_session_implementation(self):
        """Test creating a concrete Session implementation"""
        class TestSession(Session):
            def create_session(self):
                return "test_session"
        
        session = TestSession()
        assert session.create_session() == "test_session"
        assert session._log is not None
