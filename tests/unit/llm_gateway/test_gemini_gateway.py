"""Unit tests for GeminiGateway — submit_prompt takes NLQRequest, returns LLMRawResponse."""

from llm_gateway.providers import gemini_gateway
from llm_gateway.providers.gemini_gateway import GeminiGateway
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


def test_gemini_gateway_submit_prompt_success(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name
            captured["system_prompt"] = system_prompt

        async def run(self, user_message):
            captured["user_message"] = user_message
            return _FakeResult(
                '{"intent":"route_departure_options","parameters":{},'
                '"missing_params":[],"follow_up_question":null,"confidence":0.8}'
            )

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)

    gateway = GeminiGateway(api_key="key-123", model="gemini-3-flash", timeout_seconds=5)
    bundle = _make_request()

    result = gateway.submit_prompt(bundle)

    assert isinstance(result, LLMRawResponse)
    assert result.raw_response_text.startswith('{"intent":')
    assert captured["model_name"] == "google-gla:gemini-3-flash"
    assert captured["system_prompt"] == bundle.system_message
    assert captured["user_message"] == bundle.user_message


def test_gemini_gateway_prefixes_model_name_with_provider(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name

        async def run(self, user_message):
            return _FakeResult('{"intent":"x","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.5}')

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)
    gateway = GeminiGateway(api_key="key-123", model="gemini-2.5-flash")
    gateway.submit_prompt(_make_request())

    assert captured["model_name"] == "google-gla:gemini-2.5-flash"


def test_gemini_gateway_skips_prefix_when_already_qualified(monkeypatch):
    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name

        async def run(self, user_message):
            return _FakeResult('{"intent":"x","parameters":{},"missing_params":[],"follow_up_question":null,"confidence":0.5}')

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)
    gateway = GeminiGateway(api_key="key-123", model="google-gla:gemini-2.5-flash")
    gateway.submit_prompt(_make_request())

    assert captured["model_name"] == "google-gla:gemini-2.5-flash"


# ── error cases ───────────────────────────────────────────────────────────


def test_gemini_gateway_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gateway = GeminiGateway(api_key=None)
    bundle = _make_request("req-2")

    result = gateway.submit_prompt(bundle)

    assert isinstance(result, ErrorResponse)
    assert result.status == "ERROR"
    assert result.error.code == "missing_auth"
    assert "GEMINI_API_KEY" in result.error.message
    assert result.request_id == "req-2"


def test_gemini_gateway_raises_when_pydantic_ai_missing(monkeypatch):
    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", None)
    gateway = GeminiGateway(api_key="key-123")
    bundle = _make_request("req-3")

    result = gateway.submit_prompt(bundle)

    assert isinstance(result, ErrorResponse)
    assert result.status == "ERROR"
    assert result.error.code == "missing_dependency"
    assert "pydantic-ai" in result.error.message


def test_gemini_gateway_returns_error_on_timeout(monkeypatch):
    from concurrent.futures import TimeoutError as FutureTimeoutError

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            pass

        async def run(self, user_message):
            raise FutureTimeoutError()

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)
    gateway = GeminiGateway(api_key="key-123", model="gemini-3-flash", timeout_seconds=1)

    result = gateway.submit_prompt(_make_request("req-timeout"))

    assert isinstance(result, ErrorResponse)
    assert result.error.code in ("llm_timeout", "llm_gateway_failed")
