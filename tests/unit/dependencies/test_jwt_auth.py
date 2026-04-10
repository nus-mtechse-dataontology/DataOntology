from unittest.mock import Mock

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dependencies.jwt_auth import JWTAuth
from models.users import UserModel


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/protected")
    async def protected(user: UserModel = Depends(JWTAuth())):
        return {"username": user.username}

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def jwt_payload():
    return {
        "email": "user@example.com",
        "disabled": False,
        "full_name": "Test User",
        "username": "test_user",
        "exp": 9999999999,
    }


def test_jwt_auth_valid_token_returns_user(client, app, jwt_payload):
    mock_handler = Mock()
    mock_handler.verify_token.return_value = jwt_payload
    app.state.jwt_handler = mock_handler

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"username": "test_user"}
    mock_handler.verify_token.assert_called_once_with("valid-token")


def test_jwt_auth_invalid_token_returns_401(client, app):
    mock_handler = Mock()
    mock_handler.verify_token.side_effect = jwt.InvalidTokenError("bad token")
    app.state.jwt_handler = mock_handler

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_jwt_auth_expired_token_returns_401(client, app):
    mock_handler = Mock()
    mock_handler.verify_token.side_effect = jwt.ExpiredSignatureError("expired")
    app.state.jwt_handler = mock_handler

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
