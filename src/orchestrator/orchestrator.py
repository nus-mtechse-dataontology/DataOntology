"""Pipeline orchestrator for NLQ execution."""

from typing import Any, Callable

from models.common import ErrorResponse, SuccessResponse
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
        self._now_provider = now_provider

    def handle_question(self, request: NLQRequest) -> SuccessResponse[QuestionResponse] | ErrorResponse:
        del request
        raise NotImplementedError("Orchestrator.handle_question is not implemented yet.")
