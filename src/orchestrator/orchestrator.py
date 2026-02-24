"""Pipeline orchestrator for NLQ execution."""

from collections.abc import Callable
from typing import Any

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import (
    CompiledSQL,
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
    QueryPlan,
    QuestionResponse,
    ResultSet,
)


class Orchestrator:
    def __init__(
        self,
        semantic_model_provider: Callable[[], dict[str, Any]],
        prompt_builder: Callable[[str, str, dict[str, Any], str], PromptBundle],
        llm_gateway: Callable[[PromptBundle], LLMRawResponse],
        syntactic_validator: Callable[[LLMRawResponse], QueryPlan],
        semantic_validator: Callable[[QueryPlan, dict[str, Any]], QueryPlan],
        sql_compiler: Callable[[QueryPlan, dict[str, Any]], CompiledSQL],
        sql_executor: Callable[[CompiledSQL], ResultSet],
        response_builder: Callable[[ResultSet], QuestionResponse],
        error_response_builder: Callable[[ErrorResponse], ErrorResponse],
        now_provider: Callable[[], str],
    ) -> None:
        self._semantic_model_provider = semantic_model_provider
        self._prompt_builder = prompt_builder
        self._llm_gateway = llm_gateway
        self._syntactic_validator = syntactic_validator
        self._semantic_validator = semantic_validator
        self._sql_compiler = sql_compiler
        self._sql_executor = sql_executor
        self._response_builder = response_builder
        self._error_response_builder = error_response_builder
        self._now_provider = now_provider

    def handle_question(
        self, request: NLQRequest
    ) -> SuccessResponse[QuestionResponse] | ErrorResponse:
        if not isinstance(request, NLQRequest):
            request_id = "unknown"
            if isinstance(request, dict):
                candidate = request.get("request_id")
                if isinstance(candidate, str) and candidate:
                    request_id = candidate
            return self._error_response_builder(
                ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="invalid_request",
                    message="Request must be an NLQRequest",
                    component="orchestrator",
                ),
                )
            )

        semantic_model_response = self._semantic_model_provider()
        if isinstance(semantic_model_response, ErrorResponse):
            return self._error_response_builder(semantic_model_response)
        semantic_model = semantic_model_response.data

        current_time = self._now_provider()
        prompt_bundle_response = self._prompt_builder(
            request.request_id,
            request.question,
            semantic_model,
            current_time,
        )
        if isinstance(prompt_bundle_response, ErrorResponse):
            return self._error_response_builder(prompt_bundle_response)
        prompt_bundle = prompt_bundle_response.data
        if not isinstance(prompt_bundle, PromptBundle):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="prompt_builder must return SuccessResponse[PromptBundle]",
                    component="prompt_builder",
                ),
            )
            return self._error_response_builder(error)

        raw_response_response = self._llm_gateway(prompt_bundle)
        if isinstance(raw_response_response, ErrorResponse):
            return self._error_response_builder(raw_response_response)
        raw_response = raw_response_response.data
        if not isinstance(raw_response, LLMRawResponse):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="llm_gateway must return SuccessResponse[LLMRawResponse]",
                    component="llm_gateway",
                ),
            )
            return self._error_response_builder(error)

        query_plan_response = self._syntactic_validator(raw_response)
        if isinstance(query_plan_response, ErrorResponse):
            return self._error_response_builder(query_plan_response)
        query_plan = query_plan_response.data
        if not isinstance(query_plan, QueryPlan):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="syntactic_validator must return SuccessResponse[QueryPlan]",
                    component="syntactic_validator",
                ),
            )
            return self._error_response_builder(error)

        validated_query_plan_response = self._semantic_validator(query_plan, semantic_model)
        if isinstance(validated_query_plan_response, ErrorResponse):
            return self._error_response_builder(validated_query_plan_response)
        validated_query_plan = validated_query_plan_response.data
        if not isinstance(validated_query_plan, QueryPlan):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="semantic_validator must return SuccessResponse[QueryPlan]",
                    component="semantic_validator",
                ),
            )
            return self._error_response_builder(error)

        compiled_sql_response = self._sql_compiler(validated_query_plan, semantic_model)
        if isinstance(compiled_sql_response, ErrorResponse):
            return self._error_response_builder(compiled_sql_response)
        compiled_sql = compiled_sql_response.data
        if not isinstance(compiled_sql, CompiledSQL):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="sql_compiler must return SuccessResponse[CompiledSQL]",
                    component="sql_compiler",
                ),
            )
            return self._error_response_builder(error)

        result_set_response = self._sql_executor(compiled_sql)
        if isinstance(result_set_response, ErrorResponse):
            return self._error_response_builder(result_set_response)
        result_set = result_set_response.data
        if not isinstance(result_set, ResultSet):
            error = ErrorResponse(
                request_id=request.request_id,
                error=ErrorDetails(
                    code="invalid_payload",
                    message="sql_executor must return SuccessResponse[ResultSet]",
                    component="sql_executor",
                ),
            )
            return self._error_response_builder(error)

        response = self._response_builder(result_set)
        if isinstance(response, ErrorResponse):
            return self._error_response_builder(response)
        return response
