from typing import Any
from unittest.mock import Mock

import pytest

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
from orchestrator.orchestrator import Orchestrator

REQUEST_ID = "req-123"
NOW = "2026-02-24T21:30:00Z"


def _build_error(
    *,
    component: str,
    code: str = "stage_failed",
    message: str = "Stage failed",
    request_id: str = REQUEST_ID,
) -> ErrorResponse:
    return ErrorResponse(
        request_id=request_id,
        error=ErrorDetails(
            code=code,
            message=message,
            component=component,
        ),
    )


@pytest.fixture
def nlq_request() -> NLQRequest:
    return NLQRequest(request_id=REQUEST_ID, question="What is my portfolio value?")


@pytest.fixture
def payloads() -> dict[str, Any]:
    semantic_model = {"intents": {"portfolio_value": {}}}
    prompt_bundle = PromptBundle(
        request_id=REQUEST_ID,
        system_message="System",
        user_message="User",
    )
    raw_response = LLMRawResponse(
        request_id=REQUEST_ID,
        raw_response_text='{"intent":"portfolio_value"}',
    )
    query_plan = QueryPlan(
        request_id=REQUEST_ID,
        intent="portfolio_value",
        parameters={"user_id": "u-1"},
        confidence=0.92,
    )
    compiled_sql = CompiledSQL(
        request_id=REQUEST_ID,
        sql="SELECT value FROM portfolio WHERE user_id = :user_id",
        bound_params={"user_id": "u-1"},
    )
    result_set = ResultSet(
        request_id=REQUEST_ID,
        result_set=[Row(data={"value": 1000})],
    )
    question_response = QuestionResponse(
        request_id=REQUEST_ID,
        response="Your portfolio value is 1000.",
    )
    return {
        "semantic_model": semantic_model,
        "prompt_bundle": prompt_bundle,
        "raw_response": raw_response,
        "query_plan": query_plan,
        "compiled_sql": compiled_sql,
        "result_set": result_set,
        "question_response": question_response,
    }


def _success(data: Any) -> SuccessResponse[Any]:
    return SuccessResponse(request_id=REQUEST_ID, data=data)


def _build_orchestrator(
    payloads: dict[str, Any],
    *,
    semantic_model_provider: Any | None = None,
    prompt_builder: Any | None = None,
    llm_gateway: Any | None = None,
    syntactic_validator: Any | None = None,
    semantic_validator: Any | None = None,
    sql_compiler: Any | None = None,
    sql_executor: Any | None = None,
    response_builder: Any | None = None,
    now_provider: Any | None = None,
) -> tuple[Orchestrator, dict[str, Mock]]:
    mocks = {
        "semantic_model_provider": semantic_model_provider
        or Mock(return_value=_success(payloads["semantic_model"])),
        "prompt_builder": prompt_builder
        or Mock(return_value=_success(payloads["prompt_bundle"])),
        "llm_gateway": llm_gateway or Mock(return_value=_success(payloads["raw_response"])),
        "syntactic_validator": syntactic_validator
        or Mock(return_value=_success(payloads["query_plan"])),
        "semantic_validator": semantic_validator
        or Mock(return_value=_success(payloads["query_plan"])),
        "sql_compiler": sql_compiler or Mock(return_value=_success(payloads["compiled_sql"])),
        "sql_executor": sql_executor or Mock(return_value=_success(payloads["result_set"])),
        "response_builder": response_builder
        or Mock(return_value=_success(payloads["question_response"])),
        "now_provider": now_provider or Mock(return_value=NOW),
    }
    return (
        Orchestrator(
            semantic_model_provider=mocks["semantic_model_provider"],
            prompt_builder=mocks["prompt_builder"],
            llm_gateway=mocks["llm_gateway"],
            syntactic_validator=mocks["syntactic_validator"],
            semantic_validator=mocks["semantic_validator"],
            sql_compiler=mocks["sql_compiler"],
            sql_executor=mocks["sql_executor"],
            response_builder=mocks["response_builder"],
            now_provider=mocks["now_provider"],
        ),
        mocks,
    )


def _assert_error_contract(result: Any) -> None:
    assert isinstance(result, ErrorResponse)
    assert result.request_id == REQUEST_ID
    assert result.status == "ERROR"
    assert result.error.code
    assert result.error.message
    assert result.error.component


def test_handle_question_accepts_nlq_request_and_starts_pipeline(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["semantic_model_provider"].assert_called_once_with()


def test_handle_question_happy_path_returns_success_response_contract(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(payloads)

    result = orchestrator.handle_question(nlq_request)

    assert isinstance(result, SuccessResponse)
    assert result.request_id == REQUEST_ID
    assert result.status == "SUCCESS"
    assert isinstance(result.data, QuestionResponse)
    assert result.data.request_id == REQUEST_ID
    assert result.data.response


def test_handle_question_happy_path_executes_full_workflow_in_order(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    call_order: list[str] = []

    def semantic_model_provider():
        call_order.append("semantic_model_provider")
        return _success(payloads["semantic_model"])

    def prompt_builder(*args: Any):
        del args
        call_order.append("prompt_builder")
        return _success(payloads["prompt_bundle"])

    def llm_gateway(*args: Any):
        del args
        call_order.append("llm_gateway")
        return _success(payloads["raw_response"])

    def syntactic_validator(*args: Any):
        del args
        call_order.append("syntactic_validator")
        return _success(payloads["query_plan"])

    def semantic_validator(*args: Any):
        del args
        call_order.append("semantic_validator")
        return _success(payloads["query_plan"])

    def sql_compiler(*args: Any):
        del args
        call_order.append("sql_compiler")
        return _success(payloads["compiled_sql"])

    def sql_executor(*args: Any):
        del args
        call_order.append("sql_executor")
        return _success(payloads["result_set"])

    def response_builder(*args: Any):
        del args
        call_order.append("response_builder")
        return _success(payloads["question_response"])

    orchestrator, _ = _build_orchestrator(
        payloads,
        semantic_model_provider=Mock(side_effect=semantic_model_provider),
        prompt_builder=Mock(side_effect=prompt_builder),
        llm_gateway=Mock(side_effect=llm_gateway),
        syntactic_validator=Mock(side_effect=syntactic_validator),
        semantic_validator=Mock(side_effect=semantic_validator),
        sql_compiler=Mock(side_effect=sql_compiler),
        sql_executor=Mock(side_effect=sql_executor),
        response_builder=Mock(side_effect=response_builder),
    )

    orchestrator.handle_question(nlq_request)

    assert call_order == [
        "semantic_model_provider",
        "prompt_builder",
        "llm_gateway",
        "syntactic_validator",
        "semantic_validator",
        "sql_compiler",
        "sql_executor",
        "response_builder",
    ]


def test_handle_question_calls_prompt_builder_with_expected_arguments(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["prompt_builder"].assert_called_once_with(
        REQUEST_ID,
        nlq_request.question,
        payloads["semantic_model"],
        NOW,
    )


def test_handle_question_calls_llm_gateway_with_expected_prompt_bundle(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["llm_gateway"].assert_called_once_with(payloads["prompt_bundle"])


def test_handle_question_calls_syntactic_validator_with_expected_llm_raw_response(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["syntactic_validator"].assert_called_once_with(payloads["raw_response"])


def test_handle_question_calls_semantic_validator_with_expected_query_plan_and_semantic_model(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["semantic_validator"].assert_called_once_with(
        payloads["query_plan"],
        payloads["semantic_model"],
    )


def test_handle_question_calls_sql_compiler_with_expected_query_plan_and_semantic_model(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["sql_compiler"].assert_called_once_with(
        payloads["query_plan"],
        payloads["semantic_model"],
    )


def test_handle_question_calls_sql_executor_with_expected_compiled_sql(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["sql_executor"].assert_called_once_with(payloads["compiled_sql"])


def test_handle_question_calls_response_builder_with_expected_result_set(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, mocks = _build_orchestrator(payloads)

    orchestrator.handle_question(nlq_request)

    mocks["response_builder"].assert_called_once_with(payloads["result_set"])


def test_handle_question_stops_on_first_failure_and_skips_downstream_stages(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    stage_error = _build_error(component="llm_gateway", message="LLM unavailable")
    orchestrator, mocks = _build_orchestrator(
        payloads,
        llm_gateway=Mock(return_value=stage_error),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    mocks["syntactic_validator"].assert_not_called()
    mocks["semantic_validator"].assert_not_called()
    mocks["sql_compiler"].assert_not_called()
    mocks["sql_executor"].assert_not_called()


@pytest.mark.parametrize(
    "failed_stage",
    [
        "semantic_model_provider",
        "prompt_builder",
        "llm_gateway",
        "syntactic_validator",
        "semantic_validator",
        "sql_compiler",
        "sql_executor",
        "response_builder",
    ],
)
def test_handle_question_failure_at_any_stage_returns_meaningful_error_response(
    failed_stage: str,
    nlq_request: NLQRequest,
    payloads: dict[str, Any],
):
    stage_error = _build_error(component=failed_stage, message=f"{failed_stage} failed")
    orchestrator, mocks = _build_orchestrator(
        payloads,
        **{failed_stage: Mock(return_value=stage_error)},
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == failed_stage
    assert "failed" in result.error.message.lower()
    if failed_stage != "response_builder":
        mocks["response_builder"].assert_called_once()


def test_handle_question_expects_prompt_builder_success_payload_to_wrap_prompt_bundle(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        prompt_builder=Mock(return_value=_success({"not": "prompt_bundle"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "prompt_builder"


def test_handle_question_expects_llm_gateway_success_payload_to_wrap_llm_raw_response(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        llm_gateway=Mock(return_value=_success({"not": "llm_raw_response"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "llm_gateway"


def test_handle_question_expects_syntactic_validator_success_payload_to_wrap_query_plan(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        syntactic_validator=Mock(return_value=_success({"not": "query_plan"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "syntactic_validator"


def test_handle_question_expects_semantic_validator_success_payload_to_wrap_query_plan(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        semantic_validator=Mock(return_value=_success({"not": "query_plan"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "semantic_validator"


def test_handle_question_expects_sql_compiler_success_payload_to_wrap_compiled_sql(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        sql_compiler=Mock(return_value=_success({"not": "compiled_sql"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "sql_compiler"


def test_handle_question_expects_sql_executor_success_payload_to_wrap_result_set(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(
        payloads,
        sql_executor=Mock(return_value=_success({"not": "result_set"})),
    )

    result = orchestrator.handle_question(nlq_request)

    _assert_error_contract(result)
    assert result.error.component == "sql_executor"


def test_handle_question_calls_response_builder_before_final_return_on_success(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    response_builder = Mock(return_value=_success(payloads["question_response"]))
    orchestrator, _ = _build_orchestrator(
        payloads,
        response_builder=response_builder,
    )

    orchestrator.handle_question(nlq_request)

    response_builder.assert_called_once()


def test_handle_question_calls_response_builder_before_final_return_on_error(
    nlq_request: NLQRequest, payloads: dict[str, Any]
):
    stage_error = _build_error(component="llm_gateway", message="Gateway failed")
    response_builder = Mock(
        return_value=_build_error(component="response_builder", message="error response")
    )
    orchestrator, _ = _build_orchestrator(
        payloads,
        llm_gateway=Mock(return_value=stage_error),
        response_builder=response_builder,
    )

    orchestrator.handle_question(nlq_request)

    response_builder.assert_called_once_with(stage_error)


def test_handle_question_rejects_non_nlq_request_and_returns_error_response(
    payloads: dict[str, Any]
):
    orchestrator, _ = _build_orchestrator(payloads)

    result = orchestrator.handle_question({"request_id": REQUEST_ID, "question": "q"})  # type: ignore[arg-type]

    _assert_error_contract(result)
