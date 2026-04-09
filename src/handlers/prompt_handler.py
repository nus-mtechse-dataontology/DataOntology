from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails
from prompt_builder import PromptBuilder

from pathlib import Path
import traceback


class PromptHandler(AbstractHandler):
    def __init__(
            self,
            prompt_builder: PromptBuilder,
    ):
        super().__init__("PromptBuilderHandler")
        self._prompt_builder = prompt_builder
    
    def handle(self, request: NLQRequest) -> NLQRequest | SuccessResponse | ErrorResponse:
        """
        Handles the 'prompt' request type. Passes request to the next handler down the chain if criteria
        not met for this handler.
        :param request: The NLQ request
        :return: SuccessResponse or ErrorResponse
        """
        if request.request_type == "prompt":
            self._load_semantics()
            
            try:
                self._log.info("PromptBuilderHandler: Building prompt...")
                prompt_bundle = (
                    self._prompt_builder
                    .set_prompt_template(self._load_prompt())
                    .set_question(request.question)
                    .set_intent(self._semantics["intents"])
                    .set_param_schema(self._semantics["param_schema"])
                    .build()
                )
                
                self._log.info("PromptBuilderHandler: Prompt built successfully, passing to the next handler...")
                request.request_type = "llm"
                request.user_message = prompt_bundle.user_message
                request.system_message = prompt_bundle.system_message
                return super().handle(request)
        
            except Exception as error:
                self._log.error("PromptBuilderHandler: Error: Building prompt failed. %s", error)
                self._log.error(traceback.format_exc())
                return ErrorResponse(
                    request_id=request.request_id,
                    error=ErrorDetails(
                        code="prompt_build_failed",
                        message="Unable to build prompt",
                        component="prompt_builder",
                        details={"error": str(error)}
                    )
                )
        
        self._log.info("PromptHandler: Unable to process request: %s. Passing to next handler...", request.request_type)
        return super().handle(request)
    
    def _load_prompt(self) -> str:
        """
        Loads the prompt for LLM
        :return: The prompt for LLM
        """
        with open(
            Path(
                self._root,
                "resources",
                "templates",
                "query_plan_prompt.j2"
            )
        ) as pf:
            return pf.read()
