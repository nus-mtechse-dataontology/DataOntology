from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.ingestion.ingestion_routes import ingestion_router
from models.users import UserModel


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(ingestion_router)
    app.state.session = Mock()
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def enabled_user():
    return UserModel(
        email="user@example.com",
        disabled=False,
        full_name="Enabled User",
        username="enabled",
        exp=9999999999,
    )


@pytest.fixture
def disabled_user():
    return UserModel(
        email="user@example.com",
        disabled=True,
        full_name="Disabled User",
        username="disabled",
        exp=9999999999,
    )


def test_get_schema_happy_path_returns_tables(client, app, enabled_user, monkeypatch):
    async def fake_jwt_call(self, request):
        return enabled_user

    class FakeInspector:
        def get_table_names(self):
            return ["table_a"]

        def get_columns(self, table):
            return [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": False,
                    "default": None,
                    "autoincrement": True,
                    "comment": None,
                },
                {
                    "name": "name",
                    "type": "TEXT",
                    "nullable": True,
                    "default": None,
                    "autoincrement": False,
                    "comment": None,
                },
            ]

    def fake_inspect(engine):
        return FakeInspector()

    app.state.session.engine = Mock()
    monkeypatch.setattr("dependencies.jwt_auth.JWTAuth.__call__", fake_jwt_call)
    monkeypatch.setattr(
        "endpoints.routes.ingestion.ingestion_routes.inspect",
        fake_inspect,
    )

    response = client.get("/ingestion/get_schema", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tables"][0]["name"] == "table_a"
    assert payload["tables"][0]["cols"][0]["name"] == "name"


def test_get_schema_disabled_user_returns_empty_list(client, app, disabled_user, monkeypatch):
    async def fake_jwt_call(self, request):
        return disabled_user

    monkeypatch.setattr("dependencies.jwt_auth.JWTAuth.__call__", fake_jwt_call)

    response = client.get("/ingestion/get_schema", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["tables"] == []


def test_upload_happy_path_returns_status(client, app, enabled_user, monkeypatch):
    async def fake_jwt_call(self, request):
        return enabled_user

    async def fake_upload_data(session, payload):
        return {"status_code": 0, "status": "success", "records_inserted": 1}

    monkeypatch.setattr("dependencies.jwt_auth.JWTAuth.__call__", fake_jwt_call)
    monkeypatch.setattr(
        "endpoints.routes.ingestion.ingestion_routes.upload_data",
        fake_upload_data,
    )

    response = client.post(
        "/ingestion/upload",
        headers={"Authorization": "Bearer token"},
        json={"table_name": "t", "truncate": False, "data": [{"a": 1}]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_upload_disabled_user_returns_403(client, app, disabled_user, monkeypatch):
    async def fake_jwt_call(self, request):
        return disabled_user

    monkeypatch.setattr("dependencies.jwt_auth.JWTAuth.__call__", fake_jwt_call)

    response = client.post(
        "/ingestion/upload",
        headers={"Authorization": "Bearer token"},
        json={"table_name": "t", "truncate": False, "data": [{"a": 1}]},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "User does not have permission to perform this action"


def test_upload_missing_payload_fields_returns_422(client, app, enabled_user, monkeypatch):
    async def fake_jwt_call(self, request):
        return enabled_user

    monkeypatch.setattr("dependencies.jwt_auth.JWTAuth.__call__", fake_jwt_call)

    response = client.post(
        "/ingestion/upload",
        headers={"Authorization": "Bearer token"},
        json={"table_name": "t"},
    )

    assert response.status_code == 422
