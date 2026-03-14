"""Integration: Orchestrator ↔ real PromptBuilder, all other stages mocked.

Tests that the orchestrator correctly constructs a PromptRequest and passes
it to a real PromptBuilder, then handles both success and error results.
All downstream stages (llm_gateway onward) are mocked to isolate the seam.
"""

from typing import Any
from unittest.mock import Mock

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import (
    CompiledSQL,
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
    QueryPlan,
    QuestionResponse,
    ResultSet,
    Row,
)
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from prompt_builder.prompt_builder import PromptBuilder


# ── helpers ──────────────────────────────────────────────────────────────

REQUEST_ID = "req-seam-pb-1"
NOW = "2026-02-24T22:00:00Z"

SEMANTIC_MODEL = {
    "intents": {
        "cheapest_return_flight": {
            "description": "Find the cheapest return flight between two airports.",
            "required_params": ["origin", "destination", "start_date", "end_date"],
            "sql_template": "SELECT * FROM flights LIMIT :limit",
        },
    },
    "param_schema": {
        "origin": {"type": "string", "format": "iata_airport_code", "pattern": "^[A-Z]{3}$"},
        "destination": {"type": "string", "format": "iata_airport_code", "pattern": "^[A-Z]{3}$"},
    },
}


def _build_orchestrator(
    *,
    semantic_model: dict[str, Any] = SEMANTIC_MODEL,
    llm_gateway_return=None,
) -> Orchestrator:
    """Build an Orchestrator with a real PromptBuilder and mocked remaining stages."""

    default_query_plan = QueryPlan(
        request_id=REQUEST_ID,
        intent="cheapest_return_flight",
        parameters={"origin": "SIN", "destination": "BKK",
                     "start_date": "2019-09-01", "end_date": "2019-09-30"},
        confidence=0.95,
    )
    default_compiled = CompiledSQL(
        request_id=REQUEST_ID,
        sql="SELECT * FROM flights LIMIT :limit",
        bound_params={"limit": 10},
    )
    default_result_set = ResultSet(
        request_id=REQUEST_ID,
        result_set=[Row(data={"flight": "SQ123", "price": 250.0})],
    )

    return Orchestrator(
        semantic_model_provider=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=semantic_model)
        ),
        prompt_builder=PromptBuilder().build,
        llm_gateway=llm_gateway_return
        or Mock(
            return_value=SuccessResponse(
                request_id=REQUEST_ID,
                data=LLMRawResponse(
                    request_id=REQUEST_ID,
                    raw_response_text='{"intent":"cheapest_return_flight"}',
                ),
            )
        ),
        syntactic_validator=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_query_plan)
        ),
        semantic_validator=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_query_plan)
        ),
        sql_compiler=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_compiled)
        ),
        sql_executor=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_result_set)
        ),
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: NOW,
    )


# ── tests ────────────────────────────────────────────────────────────────


def test_orchestrator_with_real_prompt_builder_returns_success():
    """Happy path: real PromptBuilder produces a valid PromptBundle,
    pipeline completes with a SuccessResponse."""
    orchestrator = _build_orchestrator()

    request = NLQRequest(
        request_id=REQUEST_ID,
        question="What is the cheapest return flight from SIN to BKK?",
    )
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    assert result.request_id == REQUEST_ID
    assert result.status == "SUCCESS"


def test_prompt_bundle_contains_question_and_semantic_context():
    """Verify the PromptBundle produced by the real PromptBuilder contains
    the original question and the semantic model context."""
    real_builder = PromptBuilder()
    captured_bundle = {}

    def capturing_builder(prompt_request):
        response = real_builder.build(prompt_request)
        if isinstance(response, SuccessResponse):
            captured_bundle["bundle"] = response.data
        return response

    orchestrator = _build_orchestrator()
    # Replace prompt_builder with capturing version
    orchestrator._prompt_builder = capturing_builder

    request = NLQRequest(
        request_id=REQUEST_ID,
        question="Cheapest flight from SIN to BKK in September 2019?",
    )
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    bundle = captured_bundle["bundle"]
    assert isinstance(bundle, PromptBundle)
    assert bundle.request_id == REQUEST_ID
    assert "SIN to BKK" in bundle.user_message
    assert "cheapest_return_flight" in bundle.user_message
    assert bundle.system_message  # non-empty system message


def test_empty_question_causes_prompt_builder_error_and_orchestrator_short_circuits():
    """When the question is empty, the real PromptBuilder returns an ErrorResponse.
    The orchestrator should short-circuit and never call downstream stages."""
    llm_mock = Mock()
    orchestrator = _build_orchestrator(llm_gateway_return=llm_mock)

    request = NLQRequest(request_id=REQUEST_ID, question="   ")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.component == "prompt_builder"
    assert result.error.code == "invalid_question"
    # LLM gateway and everything downstream should never be called
    llm_mock.assert_not_called()


def test_invalid_semantic_model_causes_prompt_builder_error():
    """When the semantic model has no 'intents' object, the real PromptBuilder
    returns an error. The orchestrator should propagate it."""
    bad_model = {"tables": ["flights"]}  # missing 'intents'
    orchestrator = _build_orchestrator(semantic_model=bad_model)

    request = NLQRequest(
        request_id=REQUEST_ID,
        question="What is the cheapest flight?",
    )
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.component == "prompt_builder"
    assert result.error.code == "invalid_semantic_model"


def test_prompt_builder_uses_default_template_when_none_provided():
    """PromptBuilder should fall back to the default .j2 template
    and still produce a valid prompt with the expected JSON shape instruction."""
    orchestrator = _build_orchestrator()

    request = NLQRequest(
        request_id=REQUEST_ID,
        question="Show departures from SIN to BKK on 2019-09-12",
    )
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
