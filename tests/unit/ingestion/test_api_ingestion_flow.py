import os
import uuid

from ingestion.source.api_source.api_ingestion import ApiIngestion


class DummyGateway:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    def call_api(self, request):
        self.last_request = request
        return self.payload


class TrackingIngestion(ApiIngestion):
    def __init__(self, gateway, config):
        super().__init__(gateway, config)
        self.uploaded_payload = None

    def _upload_to_db(self, response_payload: dict):
        self.uploaded_payload = response_payload


def test_ingest_calls_gateway_and_upload(tmp_path):
    os.environ["PROJECT_PATH"] = str(tmp_path)
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "destination.apiKey").write_text("abc123")
    (vault_dir / "destination.secret").write_text("secret456")

    config = {
        "dataset": {
            "name": "test-endpoint",
            "source": {
                "method": "POST",
                "url": "https://example.com/data",
                "headers": {
                    "api_key": "api_key",
                    "x-client": "client_uuid",
                    "options": {"context": {"apiKey": "destination.apiKey"}},
                },
            },
        }
    }

    response = {"data": {"ok": True}}
    gateway = DummyGateway(response)
    ingestion = TrackingIngestion(gateway, config)

    ingestion.ingest()

    assert gateway.last_request is not None
    assert gateway.last_request.url == "https://example.com/data"
    assert gateway.last_request.headers["api_key"] == "abc123"
    assert ingestion.uploaded_payload == response


def test_generate_client_id_returns_uuid():
    ingestion = TrackingIngestion(DummyGateway({}), {"dataset": {"source": {}, "name": "x"}})
    generated = ingestion._generate_client_id()
    parsed = uuid.UUID(generated)
    assert str(parsed) == generated
