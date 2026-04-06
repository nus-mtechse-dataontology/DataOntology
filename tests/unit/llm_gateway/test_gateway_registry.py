"""Unit tests for GatewayRegistry."""

import pytest

from llm_gateway.gateway_registry import GatewayRegistry
from llm_gateway.llm_gateway import LLMGateway


class _FakeGatewayA(LLMGateway):
    def submit_prompt(self, bundle):
        pass


class _FakeGatewayB(LLMGateway):
    def submit_prompt(self, bundle):
        pass


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate each test — save and restore registry state."""
    original = GatewayRegistry._providers.copy()
    yield
    GatewayRegistry._providers.clear()
    GatewayRegistry._providers.update(original)


# ── register + get ────────────────────────────────────────────────────────


def test_register_and_get_returns_registered_class():
    GatewayRegistry.register("fake_a", _FakeGatewayA)

    assert GatewayRegistry.get("fake_a") is _FakeGatewayA


def test_get_returns_none_for_unknown_provider():
    assert GatewayRegistry.get("nonexistent") is None


def test_get_is_case_insensitive():
    GatewayRegistry.register("Gemini", _FakeGatewayA)

    assert GatewayRegistry.get("gemini") is _FakeGatewayA
    assert GatewayRegistry.get("GEMINI") is _FakeGatewayA
    assert GatewayRegistry.get("Gemini") is _FakeGatewayA


def test_register_normalises_name_to_lowercase():
    GatewayRegistry.register("OpenAI", _FakeGatewayA)

    assert GatewayRegistry.get("openai") is _FakeGatewayA


def test_register_overwrites_existing_provider():
    GatewayRegistry.register("provider", _FakeGatewayA)
    GatewayRegistry.register("provider", _FakeGatewayB)

    assert GatewayRegistry.get("provider") is _FakeGatewayB


def test_multiple_providers_registered_independently():
    GatewayRegistry.register("a", _FakeGatewayA)
    GatewayRegistry.register("b", _FakeGatewayB)

    assert GatewayRegistry.get("a") is _FakeGatewayA
    assert GatewayRegistry.get("b") is _FakeGatewayB


# ── get_all ───────────────────────────────────────────────────────────────


def test_get_all_returns_registered_providers():
    GatewayRegistry.register("a", _FakeGatewayA)
    GatewayRegistry.register("b", _FakeGatewayB)

    result = GatewayRegistry.get_all()

    assert result["a"] is _FakeGatewayA
    assert result["b"] is _FakeGatewayB


def test_get_all_returns_copy_not_reference():
    GatewayRegistry.register("a", _FakeGatewayA)

    result = GatewayRegistry.get_all()
    result["injected"] = _FakeGatewayB

    assert GatewayRegistry.get("injected") is None
