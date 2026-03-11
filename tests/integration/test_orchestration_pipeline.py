
"""Integration tests for orchestrator-to-response pipeline with faked components."""

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
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


def test_orchestrator_pipeline_with_faked_components_returns_success_contract():
    request = NLQRequest(request_id="req-int-1", question="Show my top holdings")
    semantic_model = {"intents": {"top_holdings": {}}}
    call_order: list[str] = []

    def semantic_model_provider():
        call_order.append("semantic_model_provider")
        return SuccessResponse(request_id=request.request_id, data=semantic_model)

    def prompt_builder(prompt_request: PromptRequest):
        call_order.append("prompt_builder")
        assert isinstance(prompt_request, PromptRequest)
        assert prompt_request.request_id == request.request_id
        assert prompt_request.question == request.question
        assert prompt_request.semantic_model == semantic_model
        return SuccessResponse(
            request_id=request.request_id,
            data=PromptBundle(
                request_id=request.request_id,
                system_message="system",
                user_message="user",
            ),
        )

    def llm_gateway(bundle: PromptBundle):
        call_order.append("llm_gateway")
        assert isinstance(bundle, PromptBundle)
        return SuccessResponse(
            request_id=request.request_id,
            data=LLMRawResponse(
                request_id=request.request_id,
                raw_response_text='{"intent":"top_holdings"}',
            ),
        )

    def syntactic_validator(raw: LLMRawResponse):
        call_order.append("syntactic_validator")
        assert isinstance(raw, LLMRawResponse)
        return SuccessResponse(
            request_id=request.request_id,
            data=QueryPlan(
                request_id=request.request_id,
                intent="top_holdings",
                parameters={},
                confidence=0.95,
            ),
        )

    def semantic_validator(plan: QueryPlan, model: dict):
        call_order.append("semantic_validator")
        assert isinstance(plan, QueryPlan)
        assert model == semantic_model
        return SuccessResponse(request_id=request.request_id, data=plan)

    def sql_compiler(plan: QueryPlan, model: dict):
        call_order.append("sql_compiler")
        assert isinstance(plan, QueryPlan)
        assert model == semantic_model
        return SuccessResponse(
            request_id=request.request_id,
            data=CompiledSQL(
                request_id=request.request_id,
                sql="SELECT ticker, weight FROM holdings LIMIT 2",
            ),
        )

    def sql_executor(compiled: CompiledSQL):
        call_order.append("sql_executor")
        assert isinstance(compiled, CompiledSQL)
        return SuccessResponse(
            request_id=request.request_id,
            data=ResultSet(
                request_id=request.request_id,
                result_set=[
                    Row(data={"ticker": "AAPL", "weight": 0.32}),
                    Row(data={"ticker": "MSFT", "weight": 0.26}),
                ],
            ),
        )

    orchestrator = Orchestrator(
        semantic_model_provider=semantic_model_provider,
        prompt_builder=prompt_builder,
        llm_gateway=llm_gateway,
        syntactic_validator=syntactic_validator,
        semantic_validator=semantic_validator,
        sql_compiler=sql_compiler,
        sql_executor=sql_executor,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: "2026-02-24T22:00:00Z",
    )

    result = orchestrator.handle_question(request)

    assert isinstance(result, SuccessResponse)
    assert result.request_id == request.request_id
    assert result.status == "SUCCESS"
    assert result.data.request_id == request.request_id
    assert "I found 2 matching records" in result.data.response
    assert "1." in result.data.response
    assert "2." in result.data.response
    assert call_order == [
        "semantic_model_provider",
        "prompt_builder",
        "llm_gateway",
        "syntactic_validator",
        "semantic_validator",
        "sql_compiler",
        "sql_executor",
    ]


def test_orchestrator_pipeline_with_faked_components_short_circuits_on_failure():
    request = NLQRequest(request_id="req-int-2", question="Show my top holdings")
    calls: list[str] = []

    def semantic_model_provider():
        calls.append("semantic_model_provider")
        return SuccessResponse(
            request_id=request.request_id,
            data={"intents": {"top_holdings": {}}},
        )

    def prompt_builder(prompt_request: PromptRequest):
        calls.append("prompt_builder")
        return SuccessResponse(
            request_id=request.request_id,
            data=PromptBundle(
                request_id=request.request_id,
                system_message="system",
                user_message="user",
            ),
        )

    def llm_gateway(*_args):
        calls.append("llm_gateway")
        return SuccessResponse(
            request_id=request.request_id,
            data=LLMRawResponse(request_id=request.request_id, raw_response_text="not-json"),
        )

    def syntactic_validator(*_args):
        calls.append("syntactic_validator")
        return ErrorResponse(
            request_id=request.request_id,
            error=ErrorDetails(
                code="invalid_syntax",
                message="Malformed LLM output",
                component="syntactic_validator",
            ),
        )

    def semantic_validator(*_args):
        calls.append("semantic_validator")
        return SuccessResponse(  # pragma: no cover - should never be called
            request_id=request.request_id,
            data=QueryPlan(
                request_id=request.request_id,
                intent="x",
                parameters={},
                confidence=0.5,
            ),
        )

    def sql_compiler(*_args):
        calls.append("sql_compiler")
        return SuccessResponse(  # pragma: no cover - should never be called
            request_id=request.request_id,
            data=CompiledSQL(request_id=request.request_id, sql="SELECT 1"),
        )

    def sql_executor(*_args):
        calls.append("sql_executor")
        return SuccessResponse(  # pragma: no cover - should never be called
            request_id=request.request_id,
            data=ResultSet(request_id=request.request_id),
        )

    orchestrator = Orchestrator(
        semantic_model_provider=semantic_model_provider,
        prompt_builder=prompt_builder,
        llm_gateway=llm_gateway,
        syntactic_validator=syntactic_validator,
        semantic_validator=semantic_validator,
        sql_compiler=sql_compiler,
        sql_executor=sql_executor,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: "2026-02-24T22:05:00Z",
    )

    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.request_id == request.request_id
    assert result.status == "ERROR"
    assert result.error.component == "syntactic_validator"
    assert calls == [
        "semantic_model_provider",
        "prompt_builder",
        "llm_gateway",
        "syntactic_validator",
    ]
