import pytest

from llm_gateway.providers import openai_gateway
from llm_gateway.providers.openai_gateway import OpenAIGateway
from models.pipeline import PromptBundle


class _FakeResult:
    def __init__(self, output):
        self.output = output


def test_openai_gateway_submit_prompt_success(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name
            captured["system_prompt"] = system_prompt

        def run_sync(self, user_message):
            captured["user_message"] = user_message
            return _FakeResult(
                '{"intent":"route_departure_options","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.8}'
            )

    monkeypatch.setattr(openai_gateway, "_PydanticAIAgent", _FakeAgent)

    gateway = OpenAIGateway(api_key="key-123", model="gpt-5.4-nano", timeout_seconds=5)
    bundle = PromptBundle(
        request_id="req-1",
        system_message="Return JSON only.",
        user_message="Question: show flights",
    )

    result = gateway.submit_prompt(bundle)

    assert result.request_id == bundle.request_id
    assert result.status == "SUCCESS"
    assert result.data.raw_response_text.startswith('{"intent":')
    assert captured["model_name"] == "openai:gpt-5.4-nano"
    assert captured["system_prompt"] == bundle.system_message
    assert captured["user_message"] == bundle.user_message


def test_openai_gateway_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gateway = OpenAIGateway(api_key=None)
    bundle = PromptBundle(request_id="req-2", system_message="x", user_message="y")

    result = gateway.submit_prompt(bundle)

    assert result.status == "ERROR"
    assert result.error.code == "missing_auth"
    assert "OPENAI_API_KEY" in result.error.message


def test_openai_gateway_raises_when_pydantic_ai_missing(monkeypatch):
    monkeypatch.setattr(openai_gateway, "_PydanticAIAgent", None)

    gateway = OpenAIGateway(api_key="key-123")
    bundle = PromptBundle(request_id="req-3", system_message="x", user_message="y")

    result = gateway.submit_prompt(bundle)

    assert result.status == "ERROR"
    assert result.error.code == "missing_dependency"
    assert "pydantic-ai" in result.error.message
