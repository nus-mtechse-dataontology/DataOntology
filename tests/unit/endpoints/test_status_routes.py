from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.status.status_routes import shutdown_server, status_router


def _build_client():
    app = FastAPI()
    app.include_router(status_router)
    return TestClient(app)


def test_liveness_returns_expected_shape():
    client = _build_client()

    response = client.get("/actuator/health/liveness")

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "alive"
    assert "datetime" in body
    assert "datetime_timestamp" in body
    assert "uuid" in body


def test_readiness_returns_expected_shape():
    client = _build_client()

    response = client.get("/actuator/health/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "ready"
    assert "datetime" in body
    assert "datetime_timestamp" in body
    assert "uuid" in body


def test_shutdown_route_returns_message_without_killing_process(monkeypatch):
    client = _build_client()
    monkeypatch.setattr(
        "endpoints.routes.status.status_routes.shutdown_server",
        lambda: None,
    )

    response = client.post("/actuator/shutdown/")

    assert response.status_code == 200
    assert response.json()["msg"] == "shutting down"


def test_shutdown_server_falls_back_to_force_kill(monkeypatch):
    calls = {"count": 0}

    def fake_kill(pid, sig):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr("endpoints.routes.status.status_routes.os.kill", fake_kill)
    monkeypatch.setattr(
        "endpoints.routes.status.status_routes.signal",
        SimpleNamespace(SIGTERM=15, SIGKILL=9),
    )

    shutdown_server()

    assert calls["count"] == 2
