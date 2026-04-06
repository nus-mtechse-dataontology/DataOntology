"""Unit tests for LLMGatewayFactory."""

import pytest

from llm_gateway.gateway_factory import LLMGatewayFactory
from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.llm_gateway import LLMGateway


class _FakeGateway(LLMGateway):
    def __init__(self, api_key=None, model=None, timeout_seconds=30, **kwargs):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def submit_prompt(self, bundle):
        pass


@pytest.fixture(autouse=True)
def clean_registry():
    original = GatewayRegistry._providers.copy()
    GatewayRegistry._providers.clear()
    GatewayRegistry.register("fake", _FakeGateway)
    yield
    GatewayRegistry._providers.clear()
    GatewayRegistry._providers.update(original)


# ── create ────────────────────────────────────────────────────────────────


def test_create_returns_instance_of_registered_class():
    gateway = LLMGatewayFactory.create(provider="fake")

    assert isinstance(gateway, _FakeGateway)


def test_create_passes_config_to_gateway():
    gateway = LLMGatewayFactory.create(
        provider="fake",
        api_key="key-123",
        model="test-model",
        timeout_seconds=60,
    )

    assert gateway.api_key == "key-123"
    assert gateway.model == "test-model"
    assert gateway.timeout_seconds == 60


def test_create_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMGatewayFactory.create(provider="does_not_exist")


def test_create_error_message_lists_available_providers():
    with pytest.raises(ValueError, match="fake"):
        LLMGatewayFactory.create(provider="unknown")


# ── create_from_config ────────────────────────────────────────────────────


def test_create_from_config_reads_env_vars(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("LLM_API_KEY", "env-key")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("LLM_TIMEOUT", "45")

    gateway = LLMGatewayFactory.create_from_config()

    assert isinstance(gateway, _FakeGateway)
    assert gateway.api_key == "env-key"
    assert gateway.model == "env-model"
    assert gateway.timeout_seconds == 45


def test_create_from_config_defaults_to_gemini_when_no_provider_set(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    GatewayRegistry.register("gemini", _FakeGateway)

    gateway = LLMGatewayFactory.create_from_config()

    assert isinstance(gateway, _FakeGateway)


def test_create_from_config_overrides_take_precedence_over_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("LLM_API_KEY", "env-key")

    gateway = LLMGatewayFactory.create_from_config(api_key="override-key")

    assert gateway.api_key == "override-key"


def test_create_from_config_raises_on_invalid_timeout(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("LLM_TIMEOUT", "not-a-number")

    with pytest.raises(ValueError, match="LLM_TIMEOUT"):
        LLMGatewayFactory.create_from_config()


# ── get_available_providers ───────────────────────────────────────────────


def test_get_available_providers_returns_registered():
    result = LLMGatewayFactory.get_available_providers()

    assert "fake" in result
    assert result["fake"] is _FakeGateway
