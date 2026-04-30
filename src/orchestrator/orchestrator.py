"""Pipeline orchestrator for NLQ execution."""
from handlers import *
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


class Orchestrator:
    def __init__(
        self,
        request_handler: RequestHandler,
        prompt_handler: PromptHandler,
        llm_handler: LLMHandler,
        syntactic_validation_handler: SyntacticValidationHandler,
        semantics_validation_handler: SemanticsValidationHandler,
        sql_compiler_handler: SQLCompilerHandler,
        sql_executor_handler: SQLExecutorHandler,
        response_builder_handler: ResponseFormatterHandler,
        graphdb_handler: GraphDBHandler
    ) -> None:
        self._request_handler = request_handler
        self._prompt_handler = prompt_handler
        self._llm_handler = llm_handler
        self._syntactic_validation_handler = syntactic_validation_handler
        self._semantics_validation_handler = semantics_validation_handler
        self._sql_compiler_handler = sql_compiler_handler
        self._sql_executor_handler = sql_executor_handler
        self._response_builder_handler = response_builder_handler
        
        (
            self._request_handler
            .set_next(graphdb_handler)
            .set_next(self._prompt_handler)
            .set_next(self._llm_handler)
            .set_next(self._syntactic_validation_handler)
            .set_next(self._semantics_validation_handler)
            .set_next(self._sql_compiler_handler)
            .set_next(self._sql_executor_handler)
            .set_next(self._response_builder_handler)
        )

    def handle_question(
        self, request: NLQRequest
    ) -> SuccessResponse | ErrorResponse:
        return self._request_handler.handle(request)
    