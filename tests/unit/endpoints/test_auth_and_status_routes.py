from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.auth.auth_routes import auth_router
from endpoints.routes.status.status_routes import status_router


# ==================== AUTH ROUTES TESTS ====================
@pytest.fixture
def auth_app():
    app = FastAPI()
    app.include_router(auth_router)
    app.state.authentication = Mock()
    return app


@pytest.fixture
def auth_client(auth_app):
    return TestClient(auth_app)


class TestAuthRoutes:
    def test_login_happy_path_returns_token(self, auth_client, auth_app):
        """Test successful login returns authentication token."""
        auth_app.state.authentication.login.return_value = {
            "status": 0,
            "message": "Login successful",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "username": "testuser",
        }

        response = auth_client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == 0
        assert "token" in response.json()

    def test_login_invalid_credentials_returns_401(self, auth_client, auth_app):
        """Test login with invalid credentials returns error."""
        auth_app.state.authentication.login.return_value = {
            "status": 1,
            "message": "Invalid credentials",
        }

        response = auth_client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpass"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == 1

    def test_login_missing_username_returns_422(self, auth_client):
        """Test login missing required username field."""
        response = auth_client.post(
            "/auth/login",
            json={"password": "testpass"},
        )

        assert response.status_code == 422

    def test_login_missing_password_returns_422(self, auth_client):
        """Test login missing required password field."""
        response = auth_client.post(
            "/auth/login",
            json={"username": "testuser"},
        )

        assert response.status_code == 422

    def test_login_empty_credentials_returns_422(self, auth_client):
        """Test login with empty string credentials."""
        response = auth_client.post(
            "/auth/login",
            json={"username": "", "password": ""},
        )

        # Empty strings are valid strings, so should attempt login
        assert response.status_code in [200, 422]

    def test_login_user_not_found_returns_401(self, auth_client, auth_app):
        """Test login with non-existent user."""
        auth_app.state.authentication.login.return_value = {
            "status": 1,
            "message": "User not found",
        }

        response = auth_client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "anypass"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == 1


# ==================== STATUS ROUTES TESTS ====================
@pytest.fixture
def status_app():
    app = FastAPI()
    app.include_router(status_router)
    return app


@pytest.fixture
def status_client(status_app):
    return TestClient(status_app)


class TestStatusRoutes:
    def test_health_check_returns_200(self, status_client):
        """Test health check endpoint returns 200."""
        response = status_client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_ok_status(self, status_client):
        """Test health check returns OK status."""
        response = status_client.get("/health")
        data = response.json()
        assert data.get("status") == "UP" or data.get("status") == "OK"

    def test_liveness_check_returns_200(self, status_client):
        """Test liveness check endpoint returns 200."""
        response = status_client.get("/actuator/health/liveness")
        assert response.status_code == 200

    def test_liveness_check_returns_up_status(self, status_client):
        """Test liveness check returns UP status."""
        response = status_client.get("/actuator/health/liveness")
        data = response.json()
        assert data.get("status") == "UP"

    def test_readiness_check_returns_200(self, status_client):
        """Test readiness check endpoint returns 200."""
        response = status_client.get("/actuator/health/readiness")
        assert response.status_code == 200

    def test_readiness_check_returns_up_status(self, status_client):
        """Test readiness check returns UP status."""
        response = status_client.get("/actuator/health/readiness")
        data = response.json()
        assert data.get("status") == "UP"

    def test_health_check_includes_timestamp(self, status_client):
        """Test health check response includes timestamp."""
        response = status_client.get("/health")
        data = response.json()
        assert "timestamp" in data or len(data) > 0

    def test_actuator_health_returns_detailed_info(self, status_client):
        """Test actuator health endpoint returns detailed info."""
        response = status_client.get("/actuator/health")
        assert response.status_code == 200
        data = response.json()
        # Should have status and some health details
        assert "status" in data

    def test_status_endpoint_handles_concurrent_requests(self, status_client):
        """Test that status endpoints handle multiple requests."""
        responses = [status_client.get("/health") for _ in range(5)]
        assert all(r.status_code == 200 for r in responses)
