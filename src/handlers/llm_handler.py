from handlers.abstract_handler import AbstractHandler
from llm_gateway import LLMGateway
from models import SuccessResponse, ErrorResponse, NLQRequest


class LLMHandler(AbstractHandler):
	def __init__(self, llm_gateway: LLMGateway) -> None:
		super().__init__("LLMHandler")
		self._llm_gateway = llm_gateway
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'llm' request. Passes request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ request
		:return: SuccessResponse or ErrorResponse
		"""
		if request.request_type == "llm":
			self._log.info("LLMHandler: Attempting to submit prompt to LLM..")
			llm_result = self._llm_gateway.submit_prompt(request)
			
			if isinstance(llm_result, ErrorResponse):
				self._log.error("LLMHandler: Failed to generate response from LLM...")
				self._log.error("LLMHandler: Error: %s", llm_result.error)
				return llm_result
			
			self._log.info("LLMHandler: Successfully generated response from LLM. Passing to next handler...")
			request.request_type = "syntactic"
			request.raw_response_text = llm_result.raw_response_text
			return super().handle(request)
		
		self._log.info("LLMHandler: Unable to process request: %s. Passing it to next handler...", request.request_type)
		return super().handle(request)
