import pytest

from llm_gateway.providers import gemini_gateway
from llm_gateway.providers.gemini_gateway import GeminiGateway
from models.pipeline import PromptBundle


class _FakeResult:
    def __init__(self, output):
        self.output = output


def test_gemini_gateway_submit_prompt_success(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name
            captured["system_prompt"] = system_prompt

        async def run(self, user_message):
            captured["user_message"] = user_message
            return _FakeResult(
                '{"intent":"route_departure_options","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.8}'
            )

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)

    gateway = GeminiGateway(api_key="key-123", model="gemini-3-flash", timeout_seconds=5)
    bundle = PromptBundle(
        request_id="req-1",
        system_message="Return JSON only.",
        user_message="Question: show flights",
    )

    result = gateway.submit_prompt(bundle)

    assert result.request_id == bundle.request_id
    assert result.status == "SUCCESS"
    assert result.data.raw_response_text.startswith('{"intent":')
    assert captured["model_name"] == "google-gla:gemini-3-flash"
    assert captured["system_prompt"] == bundle.system_message
    assert captured["user_message"] == bundle.user_message


def test_gemini_gateway_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gateway = GeminiGateway(api_key=None)
    bundle = PromptBundle(request_id="req-2", system_message="x", user_message="y")

    result = gateway.submit_prompt(bundle)

    assert result.status == "ERROR"
    assert result.error.code == "missing_auth"
    assert "GEMINI_API_KEY" in result.error.message


def test_gemini_gateway_raises_when_pydantic_ai_missing(monkeypatch):
    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", None)

    gateway = GeminiGateway(api_key="key-123")
    bundle = PromptBundle(request_id="req-3", system_message="x", user_message="y")

    result = gateway.submit_prompt(bundle)

    assert result.status == "ERROR"
    assert result.error.code == "missing_dependency"
    assert "pydantic-ai" in result.error.message