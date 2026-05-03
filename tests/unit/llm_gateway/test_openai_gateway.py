"""Unit tests for OpenAIGateway — submit_prompt takes NLQRequest, returns LLMRawResponse."""

from llm_gateway.providers import openai_gateway
from llm_gateway.providers.openai_gateway import OpenAIGateway
from models.common import ErrorResponse
from models.pipeline import LLMRawResponse, NLQRequest


class _FakeResult:
    def __init__(self, output):
        self.output = output


def _make_request(request_id="req-1") -> NLQRequest:
    return NLQRequest(
        request_id=request_id,
        system_message="Return JSON only.",
        user_message="Question: show flights",
    )


# ── success ───────────────────────────────────────────────────────────────


def test_openai_gateway_submit_prompt_success(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name
            captured["system_prompt"] = system_prompt

        def run_sync(self, user_message):
            captured["user_message"] = user_message
            return _FakeResult(
                '{"intent":"route_departure_options","parameters":{},'
                '"missing_params":[],"follow_up_question":null,"confidence":0.8}'
            )

    monkeypatch.setattr(openai_gateway, "PydanticAIAgent", _FakeAgent)

    gateway = OpenAIGateway(api_key="key-123", model="gpt-5.4-nano", timeout_seconds=5)
    bundle = _make_request()

    result = gateway.submit_prompt(bundle)

    assert isinstance(result, LLMRawResponse)
    assert result.raw_response_text.startswith('{"intent":')
    assert captured["model_name"] == "openai:gpt-5.4-nano"
    assert captured["system_prompt"] == bundle.system_message
    assert captured["user_message"] == bundle.user_message


def test_openai_gateway_prefixes_model_name_with_provider(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name

        def run_sync(self, user_message):
            return _FakeResult('{"intent":"x","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.5}')

    monkeypatch.setattr(openai_gateway, "PydanticAIAgent", _FakeAgent)
    gateway = OpenAIGateway(api_key="key-123", model="gpt-4o")
    gateway.submit_prompt(_make_request())

    assert captured["model_name"] == "openai:gpt-4o"


def test_openai_gateway_skips_prefix_when_already_qualified(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name

        def run_sync(self, user_message):
            return _FakeResult('{"intent":"x","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.5}')

    monkeypatch.setattr(openai_gateway, "PydanticAIAgent", _FakeAgent)
    gateway = OpenAIGateway(api_key="key-123", model="openai:gpt-4o")
    gateway.submit_prompt(_make_request())

    assert captured["model_name"] == "openai:gpt-4o"


# ── error cases ───────────────────────────────────────────────────────────


def test_openai_gateway_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gateway = OpenAIGateway(api_key=None)
    bundle = _make_request("req-2")

    result = gateway.submit_prompt(bundle)

    assert isinstance(result, ErrorResponse)
    assert result.status == "ERROR"
    assert result.error.code == "missing_auth"
    assert "OPENAI_API_KEY" in result.error.message
    assert result.request_id == "req-2"


def test_openai_gateway_returns_error_on_runtime_exception(monkeypatch):
    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            pass

        def run_sync(self, user_message):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(openai_gateway, "PydanticAIAgent", _FakeAgent)
    gateway = OpenAIGateway(api_key="key-123", model="gpt-5.4-nano", timeout_seconds=5)

    result = gateway.submit_prompt(_make_request("req-err"))

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "llm_gateway_failed"
    assert result.request_id == "req-err"
