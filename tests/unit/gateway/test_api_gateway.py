import pytest
from requests.models import PreparedRequest

from ingestion.gateway.api_gateway import ApiGateway


class DummyResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, response):
        self._resp = response

    def send(self, request):
        return self._resp


def test_call_api_success(monkeypatch):
    gateway = ApiGateway()
    dummy_req = PreparedRequest()
    dummy_req.url = "http://example"
    dummy_resp = DummyResponse(200, {"hello": "world"})
    monkeypatch.setattr(gateway, "_session", DummySession(dummy_resp))

    result = gateway.call_api(dummy_req)
    assert result == {"hello": "world"}


def test_call_api_failure(monkeypatch):
    gateway = ApiGateway()
    dummy_req = PreparedRequest()
    dummy_req.url = "http://example"
    dummy_resp = DummyResponse(404, {})
    monkeypatch.setattr(gateway, "_session", DummySession(dummy_resp))

    with pytest.raises(Exception):
        gateway.call_api(dummy_req)
