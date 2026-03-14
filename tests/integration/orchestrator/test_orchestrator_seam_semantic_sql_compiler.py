"""Seam integration: Orchestrator with real SemanticValidator + real SQLCompiler.

All other stages are mocked. Tests that a validated QueryPlan flows correctly
from SemanticValidator to SQLCompiler and that the data contract between them
holds in practice.
"""

from typing import Any
from unittest.mock import Mock

from compiler.sql_compiler import SQLCompiler
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import (
    CompiledSQL,
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
    PromptRequest,
    QueryPlan,
    ResultSet,
    Row,
)
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder
from validators.semantic.semantic_validator import SemanticValidator


# ── helpers ──────────────────────────────────────────────────────────────

REQUEST_ID = "req-seam-sv-sc-1"
NOW = "2026-02-24T22:00:00Z"

SEMANTIC_MODEL = {
    "intents": {
        "cheapest_return_flight": {
            "description": "Find the cheapest return flight between two airports.",
            "required_params": ["origin", "destination", "start_date", "end_date"],
            "sql_template": (
                "SELECT sr.session_id, MIN(r.fare_total_amount) AS cheapest_return_price "
                "FROM search_response sr "
                "JOIN recommendation r ON r.payload_id = sr.payload_id "
                "WHERE f_out.origin_airport_code = :origin "
                "AND f_out.destination_airport_code = :destination "
                "AND date(f_out.departure_date) BETWEEN date(:start_date) AND date(:end_date) "
                "LIMIT :limit"
            ),
        },
        "destinations_under_budget_return": {
            "description": "List destinations under budget.",
            "required_params": ["origin", "max_price", "start_date", "end_date"],
            "sql_template": (
                "SELECT DISTINCT f_out.destination_airport_code AS destination "
                "FROM search_response sr "
                "WHERE f_out.origin_airport_code = :origin "
                "AND date(f_out.departure_date) BETWEEN date(:start_date) AND date(:end_date) "
                "HAVING MIN(r.fare_total_amount) <= :max_price "
                "LIMIT :limit"
            ),
        },
    },
    "param_schema": {
        "origin": {"type": "string", "format": "iata_airport_code", "pattern": "^[A-Z]{3}$"},
        "destination": {"type": "string", "format": "iata_airport_code", "pattern": "^[A-Z]{3}$"},
        "start_date": {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "end_date": {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "max_price": {"type": "number", "minimum": 0},
    },
}


def _make_query_plan(
    intent: str = "cheapest_return_flight",
    parameters: dict[str, Any] | None = None,
    missing_params: list[str] | None = None,
    confidence: float = 0.95,
) -> QueryPlan:
    return QueryPlan(
        request_id=REQUEST_ID,
        intent=intent,
        parameters=parameters or {
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        },
        missing_params=missing_params or [],
        confidence=confidence,
    )


def _build_orchestrator(
    *,
    query_plan: QueryPlan | None = None,
    sql_executor_mock: Mock | None = None,
) -> Orchestrator:
    """Build an Orchestrator with real SemanticValidator + real SQLCompiler,
    everything else mocked."""

    plan = query_plan or _make_query_plan()
    default_result_set = ResultSet(
        request_id=REQUEST_ID,
        result_set=[Row(data={"session_id": "s1", "cheapest_return_price": 180.0})],
    )

    semantic_validator = SemanticValidator()
    sql_compiler = SQLCompiler()

    return Orchestrator(
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
                data=LLMRawResponse(request_id=REQUEST_ID, raw_response_text="{}"),
            )
        ),
        syntactic_validator=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=plan)
        ),
        semantic_validator=semantic_validator.validate,
        sql_compiler=sql_compiler.compile,
        sql_executor=sql_executor_mock
        or Mock(return_value=SuccessResponse(request_id=REQUEST_ID, data=default_result_set)),
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: NOW,
    )


# ── tests ────────────────────────────────────────────────────────────────


def test_valid_plan_passes_semantic_validation_and_compiles_sql():
    """Happy path: a valid QueryPlan passes SemanticValidator and
    SQLCompiler produces parameterized SQL with bound params."""
    sql_executor_mock = Mock(
        return_value=SuccessResponse(
            request_id=REQUEST_ID,
            data=ResultSet(request_id=REQUEST_ID, result_set=[]),
        )
    )
    orchestrator = _build_orchestrator(sql_executor_mock=sql_executor_mock)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight SIN to BKK?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    # Verify SQLExecutor received a CompiledSQL from the real SQLCompiler
    sql_executor_mock.assert_called_once()
    compiled_sql = sql_executor_mock.call_args[0][0]
    assert isinstance(compiled_sql, CompiledSQL)
    assert compiled_sql.bound_params["origin"] == "SIN"
    assert compiled_sql.bound_params["destination"] == "BKK"
    assert ":origin" in compiled_sql.sql
    assert ":destination" in compiled_sql.sql


def test_compiled_sql_includes_default_limit():
    """SQLCompiler should add a default limit of 10 when not specified in parameters."""
    sql_executor_mock = Mock(
        return_value=SuccessResponse(
            request_id=REQUEST_ID,
            data=ResultSet(request_id=REQUEST_ID, result_set=[]),
        )
    )
    orchestrator = _build_orchestrator(sql_executor_mock=sql_executor_mock)

    request = NLQRequest(request_id=REQUEST_ID, question="Cheapest flight?")
    orchestrator.handle_question(request)

    compiled_sql = sql_executor_mock.call_args[0][0]
    assert compiled_sql.bound_params["limit"] == 10


def test_invalid_intent_rejected_by_semantic_validator_before_sql_compiler():
    """SemanticValidator rejects an unknown intent before SQLCompiler runs."""
    plan = _make_query_plan(intent="nonexistent_intent")
    sql_executor_mock = Mock()
    orchestrator = _build_orchestrator(
        query_plan=plan,
        sql_executor_mock=sql_executor_mock,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Unknown intent query")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_intent"
    assert result.error.component == "semantic_validator"
    sql_executor_mock.assert_not_called()


def test_missing_required_params_rejected_before_sql_compiler():
    """SemanticValidator rejects when required params are missing."""
    plan = _make_query_plan(parameters={"origin": "SIN"})  # missing 3 required params
    sql_executor_mock = Mock()
    orchestrator = _build_orchestrator(
        query_plan=plan,
        sql_executor_mock=sql_executor_mock,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Cheap flights from SIN")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "missing_required_params"
    assert result.error.component == "semantic_validator"
    sql_executor_mock.assert_not_called()


def test_invalid_param_format_rejected_before_sql_compiler():
    """SemanticValidator rejects params that don't match param_schema patterns."""
    plan = _make_query_plan(
        parameters={
            "origin": "singapore",  # not IATA format
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        }
    )
    sql_executor_mock = Mock()
    orchestrator = _build_orchestrator(
        query_plan=plan,
        sql_executor_mock=sql_executor_mock,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Flights from singapore to BKK")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "invalid_param_format"
    assert result.error.component == "semantic_validator"
    sql_executor_mock.assert_not_called()


def test_different_intent_compiles_correct_sql_template():
    """Each intent should compile to its own SQL template."""
    plan = _make_query_plan(
        intent="destinations_under_budget_return",
        parameters={
            "origin": "SIN",
            "max_price": 300,
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        },
    )
    sql_executor_mock = Mock(
        return_value=SuccessResponse(
            request_id=REQUEST_ID,
            data=ResultSet(request_id=REQUEST_ID, result_set=[]),
        )
    )
    orchestrator = _build_orchestrator(
        query_plan=plan,
        sql_executor_mock=sql_executor_mock,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Where can I fly under 300?")
    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    compiled_sql = sql_executor_mock.call_args[0][0]
    assert compiled_sql.bound_params["origin"] == "SIN"
    assert compiled_sql.bound_params["max_price"] == 300
    assert ":max_price" in compiled_sql.sql


def test_llm_flagged_missing_params_rejected_before_sql_compiler():
    """When the LLM flags missing_params, SemanticValidator rejects before SQL."""
    plan = _make_query_plan(
        parameters={
            "origin": "SIN",
            "destination": "BKK",
            "start_date": "2019-09-01",
            "end_date": "2019-09-30",
        },
        missing_params=["end_date"],
    )
    sql_executor_mock = Mock()
    orchestrator = _build_orchestrator(
        query_plan=plan,
        sql_executor_mock=sql_executor_mock,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Flights from SIN to BKK")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "llm_flagged_missing_params"
    sql_executor_mock.assert_not_called()
