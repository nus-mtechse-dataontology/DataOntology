"""Seam integration: Orchestrator with real SyntacticValidator.

All other stages are mocked. Tests that raw LLM output is correctly parsed
into a QueryPlan by the real SyntacticValidator, and that the orchestrator
properly handles both success and error results.
"""

import json
from typing import Any
from unittest.mock import Mock

from models.common import ErrorResponse, SuccessResponse
from models.pipeline import (
    CompiledSQL,
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
    QueryPlan,
    ResultSet,
    Row,
)
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from validators.syntactic.syntactic_validator import SyntacticValidator


# ── helpers ──────────────────────────────────────────────────────────────

REQUEST_ID = "req-seam-sv-1"
NOW = "2026-02-24T22:00:00Z"
SEMANTIC_MODEL = {"intents": {"cheapest_return_flight": {}}}


def _build_orchestrator(
    *,
    llm_raw_text: str,
    semantic_validator_mock: Mock | None = None,
) -> tuple[Orchestrator, dict[str, Mock]]:
    """Build an Orchestrator with a real SyntacticValidator, everything else mocked."""

    syntactic_validator = SyntacticValidator()

    # Default downstream mocks
    default_plan = QueryPlan(
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
        result_set=[Row(data={"price": 180.0})],
    )

    sem_mock = semantic_validator_mock or Mock(
        return_value=SuccessResponse(request_id=REQUEST_ID, data=default_plan)
    )
    sql_compiler_mock = Mock(
        return_value=SuccessResponse(request_id=REQUEST_ID, data=default_compiled)
    )
    sql_executor_mock = Mock(
        return_value=SuccessResponse(request_id=REQUEST_ID, data=default_result_set)
    )

    orchestrator = Orchestrator(
        semantic_model_provider=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=SEMANTIC_MODEL)
        ),
        prompt_builder=Mock(
            return_value=SuccessResponse(
                request_id=REQUEST_ID,
                data=PromptBundle(
                    request_id=REQUEST_ID,
                    system_message="system",
                    user_message="user",
                ),
            )
        ),
        llm_gateway=Mock(
            return_value=SuccessResponse(
                request_id=REQUEST_ID,
                data=LLMRawResponse(request_id=REQUEST_ID, raw_response_text=llm_raw_text),
            )
        ),
        syntactic_validator=syntactic_validator.validate,
        semantic_validator=sem_mock,
        sql_compiler=sql_compiler_mock,
        sql_executor=sql_executor_mock,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: NOW,
    )

    mocks = {
        "semantic_validator": sem_mock,
        "sql_compiler": sql_compiler_mock,
        "sql_executor": sql_executor_mock,
    }
    return orchestrator, mocks


# ── tests ────────────────────────────────────────────────────────────────


def test_valid_json_parsed_into_query_plan_and_passed_downstream():
    """Happy path: valid JSON from LLM → SyntacticValidator parses it →
    orchestrator passes the QueryPlan to semantic_validator."""
    llm_json = json.dumps({
        "intent": "cheapest_return_flight",
        "parameters": {"origin": "SIN", "destination": "BKK",
                        "start_date": "2019-09-01", "end_date": "2019-09-30"},
        "missing_params": [],
        "follow_up_question": None,
        "confidence": 0.92,
    })
    orchestrator, mocks = _build_orchestrator(llm_raw_text=llm_json)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    # Verify semantic_validator received a real QueryPlan from SyntacticValidator
    mocks["semantic_validator"].assert_called_once()
    query_plan = mocks["semantic_validator"].call_args[0][0]
    assert isinstance(query_plan, QueryPlan)
    assert query_plan.intent == "cheapest_return_flight"
    assert query_plan.confidence == 0.92
    assert query_plan.parameters["origin"] == "SIN"
    assert query_plan.request_id == REQUEST_ID


def test_markdown_fenced_json_is_stripped_and_parsed():
    """SyntacticValidator strips markdown fences before parsing JSON."""
    raw_json = json.dumps({
        "intent": "cheapest_return_flight",
        "parameters": {},
        "missing_params": [],
        "follow_up_question": None,
        "confidence": 0.85,
    })
    llm_text = f"```json\n{raw_json}\n```"
    orchestrator, mocks = _build_orchestrator(llm_raw_text=llm_text)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    query_plan = mocks["semantic_validator"].call_args[0][0]
    assert query_plan.intent == "cheapest_return_flight"
    assert query_plan.confidence == 0.85


def test_malformed_json_returns_error_and_short_circuits():
    """Malformed JSON from LLM → SyntacticValidator error → downstream never called."""
    orchestrator, mocks = _build_orchestrator(llm_raw_text="{ not valid json }")

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "malformed_json"
    assert result.error.component == "syntactic_validator"
    mocks["semantic_validator"].assert_not_called()
    mocks["sql_compiler"].assert_not_called()
    mocks["sql_executor"].assert_not_called()


def test_missing_required_fields_returns_schema_error():
    """JSON missing required QueryPlan fields → schema validation error."""
    llm_json = json.dumps({"parameters": {}})  # missing intent, confidence
    orchestrator, mocks = _build_orchestrator(llm_raw_text=llm_json)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "schema_validation_error"
    assert result.error.component == "syntactic_validator"
    mocks["semantic_validator"].assert_not_called()


def test_confidence_out_of_range_returns_error():
    """Confidence > 1.0 → SyntacticValidator rejects before downstream stages."""
    llm_json = json.dumps({
        "intent": "cheapest_return_flight",
        "parameters": {},
        "missing_params": [],
        "follow_up_question": None,
        "confidence": 1.5,
    })
    orchestrator, mocks = _build_orchestrator(llm_raw_text=llm_json)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_confidence"
    assert result.error.component == "syntactic_validator"
    mocks["semantic_validator"].assert_not_called()


def test_empty_llm_response_returns_malformed_json():
    """Empty string from LLM → malformed JSON error."""
    orchestrator, mocks = _build_orchestrator(llm_raw_text="")

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "malformed_json"
    mocks["semantic_validator"].assert_not_called()


def test_query_plan_preserves_follow_up_question():
    """SyntacticValidator preserves follow_up_question and missing_params from LLM."""
    llm_json = json.dumps({
        "intent": "cheapest_return_flight",
        "parameters": {"origin": "SIN"},
        "missing_params": ["destination", "start_date", "end_date"],
        "follow_up_question": "Which city do you want to fly to?",
        "confidence": 0.6,
    })
    orchestrator, mocks = _build_orchestrator(llm_raw_text=llm_json)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheap flights from Singapore")
    orchestrator.handle_question(request)

    query_plan = mocks["semantic_validator"].call_args[0][0]
    assert query_plan.missing_params == ["destination", "start_date", "end_date"]
    assert query_plan.follow_up_question == "Which city do you want to fly to?"
    assert query_plan.confidence == 0.6
