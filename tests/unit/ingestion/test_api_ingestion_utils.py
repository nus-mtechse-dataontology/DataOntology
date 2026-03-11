import os
from ingestion.source.api_source.api_ingestion import ApiIngestion


class DummyIngestion(ApiIngestion):
    def __init__(self):
        # provide minimal config since parent uses it in __init__
        super().__init__(api_gateway=None, config={})

    def _upload_to_db(self, response_payload: dict):
        pass


def test_get_vault(tmp_path):
    # set up temporary project path and vault file
    os.environ["PROJECT_PATH"] = str(tmp_path)
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "foo.key").write_text("supersecret")

    dummy = DummyIngestion()
    assert dummy._get_vault("foo.key") == "supersecret"


def test_replace_context(tmp_path):
    os.environ["PROJECT_PATH"] = str(tmp_path)
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "a.key").write_text("value123")

    dummy = DummyIngestion()
    payload = {"api_key": "api_key", "options": {"context": {"apiKey": "a.key"}}}
    replaced = dummy._replace_context(payload)
    assert replaced["api_key"] == "value123"
    # options should be removed
    assert "options" not in replaced
