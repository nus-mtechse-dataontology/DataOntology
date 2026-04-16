"""Unit tests for LLMGatewayFactory."""

import pytest

from llm_gateway.gateway_factory import LLMGatewayFactory
from llm_gateway.llm_gateway import LLMGateway


class _FakeGateway(LLMGateway):
    def __init__(self, api_key=None, model=None, timeout_seconds=30, **kwargs):
        super().__init__(api_key=api_key, model=model or "fake-default", timeout_seconds=timeout_seconds)

    def submit_prompt(self, bundle):
        pass


@pytest.fixture()
def fake_provider_map(monkeypatch):
    monkeypatch.setattr(LLMGatewayFactory, "_PROVIDERS", {"fake": _FakeGateway})
    yield


# ── create ────────────────────────────────────────────────────────────────


def test_create_returns_instance_of_registered_class(fake_provider_map):
    gateway = LLMGatewayFactory.create(provider="fake")

    assert isinstance(gateway, _FakeGateway)


def test_create_passes_config_to_gateway(fake_provider_map):
    gateway = LLMGatewayFactory.create(
        provider="fake",
        api_key="key-123",
        model="test-model",
        timeout_seconds=60,
    )

    assert gateway._api_key == "key-123"
    assert gateway._model == "test-model"
    assert gateway._timeout_seconds == 60


def test_create_raises_for_unknown_provider(fake_provider_map):
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMGatewayFactory.create(provider="does_not_exist")


def test_create_error_message_lists_available_providers(fake_provider_map):
    with pytest.raises(ValueError, match="fake"):
        LLMGatewayFactory.create(provider="unknown")
