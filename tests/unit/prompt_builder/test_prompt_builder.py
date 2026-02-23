import json

from models.common import ErrorResponse, SuccessResponse
from models.pipeline import PromptBundle, PromptRequest
from prompt_builder import PromptBuilder


def test_build_prompt_success_contains_required_context_and_structure():
    template = """Question: {question}\nCurrent time: {current_time}\nSemantic model: {semantic_model}"""
    request = PromptRequest(
        request_id="req-1",
        question="What is the cheapest return flight from SIN to BKK?",
        prompt_template=template,
        semantic_model={
            "intents": {
                "cheapest_return_flight": {
                    "required_params": ["origin", "destination", "start_date", "end_date"]
                }
            },
            "param_schema": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
            },
        },
    )

    response = PromptBuilder().build(request)

    assert isinstance(response, SuccessResponse)
    assert response.request_id == request.request_id
    assert response.status == "SUCCESS"
    assert isinstance(response.data, PromptBundle)

    payload = response.data.user_message
    assert request.question in payload
    assert "semantic_whitelist" in payload
    assert "valid JSON" in response.data.system_message

    semantic_block = payload.split("Semantic model: ", maxsplit=1)[1]
    parsed = json.loads(semantic_block)
    assert "intents" in parsed["semantic_whitelist"]


def test_build_prompt_returns_error_for_invalid_template_placeholders():
    request = PromptRequest(
        request_id="req-2",
        question="Find options",
        prompt_template="Question: {question} Unknown: {missing_field}",
        semantic_model={"intents": {"route_departure_options": {}}},
    )

    response = PromptBuilder().build(request)

    assert isinstance(response, ErrorResponse)
    assert response.request_id == request.request_id
    assert response.status == "ERROR"
    assert response.error.code == "invalid_prompt_template"
    assert response.error.component == "prompt_builder"


def test_build_prompt_returns_error_for_invalid_semantic_model():
    request = PromptRequest(
        request_id="req-3",
        question="Find options",
        prompt_template="Question: {question}",
        semantic_model={"version": "1.0"},
    )

    response = PromptBuilder().build(request)

    assert isinstance(response, ErrorResponse)
    assert response.request_id == request.request_id
    assert response.error.code == "invalid_semantic_model"


def test_build_prompt_uses_default_query_plan_template_when_empty_template():
    request = PromptRequest(
        request_id="req-4",
        question="Show return fare options from SIN to BKK.",
        prompt_template="",
        semantic_model={
            "intents": {
                "return_fare_options": {
                    "required_params": ["origin", "destination", "start_date", "end_date"]
                }
            },
            "param_schema": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
            },
        },
    )

    response = PromptBuilder().build(request)

    assert isinstance(response, SuccessResponse)
    assert response.status == "SUCCESS"
    assert "Role: You are an AI query planner for flight analytics." in response.data.user_message
    assert request.question in response.data.user_message
    assert "Semantic context:" in response.data.user_message
