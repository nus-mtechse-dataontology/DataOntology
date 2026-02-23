"""Integration tests for orchestration pipeline components."""

import json

from llm_gateway.providers.gemini_gateway import GeminiGateway
from models.pipeline import PromptRequest, LLMRawResponse
from prompt_builder.prompt_builder import PromptBuilder


class _FakeResult:
    def __init__(self, output):
        self.output = output


def test_prompt_builder_to_gemini_gateway_chain(monkeypatch):
    """Test PromptBuilder output feeds seamlessly into GeminiGateway."""
    from llm_gateway.providers import gemini_gateway

    captured = {}

    class _FakeAgent:
        def __init__(self, model_name, system_prompt):
            captured["model_name"] = model_name
            captured["system_prompt"] = system_prompt

        def run_sync(self, user_message):
            captured["user_message"] = user_message
            return _FakeResult(
                json.dumps({
                    "intent": "cheapest_return_flight",
                    "parameters": {
                        "origin": "SIN",
                        "destination": "BKK",
                        "start_date": "2019-09-01",
                        "end_date": "2019-09-30"
                    },
                    "missing_params": [],
                    "follow_up_question": None,
                    "confidence": 0.95
                })
            )

    monkeypatch.setattr(gemini_gateway, "_PydanticAIAgent", _FakeAgent)

    template = """Question: {question}
Current time: {current_time}
Semantic model: {semantic_model}

Extract the intent and parameters from the question above."""

    semantic_model = {
        "intents": {
            "cheapest_return_flight": {
                "description": "Find the lowest-priced return flight",
                "required_params": ["origin", "destination", "start_date", "end_date"]
            },
            "route_departure_options": {
                "description": "Return departure options",
                "required_params": ["origin", "destination", "start_date", "end_date"]
            }
        },
        "param_schema": {
            "origin": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "destination": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"}
        }
    }

    request = PromptRequest(
        request_id="req-123",
        question="What is the cheapest return flight from SIN to BKK in September 2019?",
        prompt_template=template,
        semantic_model=semantic_model,
    )

    builder = PromptBuilder()
    build_response = builder.build(request)

    assert build_response.status == "SUCCESS"
    prompt_bundle = build_response.data
    assert prompt_bundle.request_id == request.request_id
    assert request.question in prompt_bundle.user_message

    gateway = GeminiGateway(api_key="test-key-123")
    llm_response = gateway.submit_prompt(prompt_bundle)

    assert isinstance(llm_response, LLMRawResponse)
    assert llm_response.request_id == request.request_id

    response_json = json.loads(llm_response.raw_response_text)
    assert response_json["intent"] == "cheapest_return_flight"
    assert response_json["parameters"]["origin"] == "SIN"
    assert response_json["confidence"] == 0.95

    assert "You are an NLQ planner" in captured["system_prompt"]
    assert "cheapest_return_flight" in captured["user_message"]
    assert "Return only valid JSON" in captured["user_message"]
