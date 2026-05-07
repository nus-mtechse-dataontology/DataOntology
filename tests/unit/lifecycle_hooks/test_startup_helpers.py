from pathlib import Path
from types import SimpleNamespace

import pytest

import lifecycle_hooks.startup as startup


def test_load_env_loads_both_files(tmp_path, monkeypatch):
    calls = []

    def fake_load_dotenv(path, override=False):
        calls.append((Path(path).name, override))

    monkeypatch.setattr(startup, "load_dotenv", fake_load_dotenv)

    startup.load_env(tmp_path)

    assert calls == [(".env", False), ("local.env", False)]


def test_load_config_reads_project_path(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "config.toml").write_text(
        """
[jwt]
expire_mins = 15
algo = "HS256"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PROJECT_PATH", str(tmp_path))

    config = startup.load_config()

    assert config["jwt"]["expire_mins"] == 15
    assert config["jwt"]["algo"] == "HS256"


def test_get_key_returns_token_string():
    key = startup.get_key()

    assert isinstance(key, str)
    assert key


def test_setup_telegram_handler_builds_handler(monkeypatch):
    created = {}

    class FakeMapper:
        pass

    class FakeClient:
        def __init__(self, token):
            created["token"] = token

    class FakeHandler:
        def __init__(self, mapper, orchestrator, client):
            created["mapper"] = mapper
            created["orchestrator"] = orchestrator
            created["client"] = client

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setattr(startup, "TelegramUpdateMapper", FakeMapper)
    monkeypatch.setattr(startup, "TelegramClient", FakeClient)
    monkeypatch.setattr(startup, "TelegramWebhookHandler", FakeHandler)

    handler = startup.setup_telegram_handler("orch")

    assert isinstance(handler, FakeHandler)
    assert created["token"] == "secret-token"
    assert isinstance(created["mapper"], FakeMapper)
    assert created["orchestrator"] == "orch"
