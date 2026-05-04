import pytest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.auth.auth_routes import authenticate_user, auth_router


def _build_client(auth_service):
    app = FastAPI()
    app.state.auth = auth_service
    app.include_router(auth_router)
    return TestClient(app)


@pytest.mark.anyio
async def test_authenticate_user_helper_returns_success_shape():
    auth = Mock()
    auth.authenticate_user.return_value = {
        "verified": True,
        "message": "ok",
        "access_token": "token",
        "full_name": "Test User",
        "token_type": "bearer",
    }

    result = await authenticate_user(auth, "test_user", "password")

    assert result["status_code"] == 200
    assert result["message"] == "ok"
    assert result["access_token"] == "token"
    assert result["token_type"] == "bearer"


def test_login_route_returns_token_payload():
    auth = Mock()
    auth.authenticate_user.return_value = {
        "verified": True,
        "message": "logged in",
        "access_token": "abc123",
        "full_name": "Test User",
        "token_type": "bearer",
    }
    client = _build_client(auth)

    response = client.post(
        "/auth/login",
        data={"username": "test_user", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "logged in"
    assert response.json()["access_token"] == "abc123"
    auth.authenticate_user.assert_called_once_with("test_user", "secret")
