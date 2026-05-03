import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from endpoints.routes.status.status_routes import status_router
from fastapi import FastAPI


@pytest.fixture
def status_app():
    """Create FastAPI app with status router"""
    app = FastAPI()
    app.include_router(status_router)
    return app


@pytest.fixture
def status_client(status_app):
    """FastAPI test client"""
    return TestClient(status_app)


class TestStatusRoutes:
    """Test status/health endpoint routes"""
    
    def test_liveness_endpoint_returns_200(self, status_client):
        """Test liveness endpoint returns 200 status"""
        response = status_client.get('/actuator/health/liveness')
        assert response.status_code == 200
    
    def test_liveness_endpoint_response_structure(self, status_client):
        """Test liveness endpoint response contains required fields"""
        response = status_client.get('/actuator/health/liveness')
        data = response.json()
        
        assert 'msg' in data
        assert data['msg'] == 'alive'
        assert 'datetime' in data
        assert 'datetime_timestamp' in data
        assert 'uuid' in data
    
    def test_liveness_endpoint_datetime_format(self, status_client):
        """Test liveness endpoint datetime is properly formatted"""
        response = status_client.get('/actuator/health/liveness')
        data = response.json()
        
        # Verify datetime format YYYY-MM-DD HH:MM:SS
        datetime_str = data['datetime']
        parsed = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        assert parsed is not None
    
    def test_liveness_endpoint_timestamp_is_integer(self, status_client):
        """Test liveness endpoint timestamp is integer"""
        response = status_client.get('/actuator/health/liveness')
        data = response.json()
        
        assert isinstance(data['datetime_timestamp'], int)
        assert data['datetime_timestamp'] > 0
    
    def test_liveness_endpoint_uuid_format(self, status_client):
        """Test liveness endpoint returns valid UUID"""
        response = status_client.get('/actuator/health/liveness')
        data = response.json()
        
        uuid_str = data['uuid']
        # UUID format check: 8-4-4-4-12 hex characters
        assert len(uuid_str) == 36
        assert uuid_str.count('-') == 4
    
    def test_readiness_endpoint_returns_200(self, status_client):
        """Test readiness endpoint returns 200 status"""
        response = status_client.get('/actuator/health/readiness')
        assert response.status_code == 200
    
    def test_readiness_endpoint_response_structure(self, status_client):
        """Test readiness endpoint response contains required fields"""
        response = status_client.get('/actuator/health/readiness')
        data = response.json()
        
        assert 'msg' in data
        assert data['msg'] == 'ready'
        assert 'datetime' in data
        assert 'datetime_timestamp' in data
    
    def test_readiness_endpoint_has_uuid(self, status_client):
        """Test readiness endpoint returns UUID"""
        response = status_client.get('/actuator/health/readiness')
        data = response.json()
        
        assert 'uuid' in data
        uuid_str = data['uuid']
        assert len(uuid_str) == 36
    
    def test_multiple_liveness_calls_return_different_uuids(self, status_client):
        """Test that multiple liveness calls return different UUIDs"""
        response1 = status_client.get('/actuator/health/liveness')
        response2 = status_client.get('/actuator/health/liveness')
        
        uuid1 = response1.json()['uuid']
        uuid2 = response2.json()['uuid']
        
        # UUIDs should be different (generated fresh each time)
        assert uuid1 != uuid2
    
    def test_liveness_content_type(self, status_client):
        """Test liveness endpoint returns JSON content type"""
        response = status_client.get('/actuator/health/liveness')
        assert response.headers['content-type'] == 'application/json'
    
    def test_readiness_content_type(self, status_client):
        """Test readiness endpoint returns JSON content type"""
        response = status_client.get('/actuator/health/readiness')
        assert response.headers['content-type'] == 'application/json'
    
    def test_status_router_tag(self):
        """Test status router has correct tag"""
        assert status_router.tags == ["Status"]
    
    def test_status_router_prefix(self):
        """Test status router has correct prefix"""
        assert status_router.prefix == '/actuator'
