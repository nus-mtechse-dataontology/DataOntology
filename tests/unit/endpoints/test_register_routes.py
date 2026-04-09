from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.register.register_routes import register_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(register_router)
    app.state.registration = Mock()
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_register_new_account_happy_path_returns_200(client, app):
    app.state.registration.register_user.return_value = {
        "status": 0,
        "message": "User registered",
        "username": "new_user",
        "full_name": "New User",
    }

    response = client.post(
        "/register/new",
        json={
            "username": "new_user",
            "password": "secret",
            "email": "new@example.com",
            "full_name": "New User",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == 0


def test_register_existing_user_returns_200_with_status_1(client, app):
    app.state.registration.register_user.return_value = {
        "status": 1,
        "message": "User already exists",
        "username": "existing",
    }

    response = client.post(
        "/register/new",
        json={
            "username": "existing",
            "password": "secret",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == 1


def test_register_missing_required_fields_returns_422(client):
    response = client.post("/register/new", json={"username": "u"})
    assert response.status_code == 422


def test_register_empty_username_edge_case_returns_200(client, app):
    app.state.registration.register_user.return_value = {
        "status": 0,
        "message": "User registered",
        "username": "",
        "full_name": None,
    }

    response = client.post(
        "/register/new",
        json={"username": "", "password": "secret"},
    )

    assert response.status_code == 200
