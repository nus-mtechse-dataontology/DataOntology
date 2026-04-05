from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest
from validators import SyntacticValidator


class SyntacticValidationHandler(AbstractHandler):
	def __init__(self, syntactic_validator: SyntacticValidator):
		super().__init__("SyntacticValidationHandler")
		self._syntactic_validator = syntactic_validator
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'syntactic' request. Passes request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		if request.request_type == "syntactic":
			self._log.info("SyntacticValidationHandler: Validating syntactic response from LLM..")
			syntactic_res = self._syntactic_validator.validate(request)
			
			if isinstance(syntactic_res, ErrorResponse):
				self._log.error("SyntacticValidationHandler: syntactic is not valid...")
				self._log.error("SyntacticValidationHandler: Error: %s", syntactic_res.error)
				return syntactic_res
			
			self._log.info("SyntacticValidationHandler: Successfully validated syntactic, passing to next handler...")
			request.request_type = "semantics"
			request.query_plan = syntactic_res.data
			return super().handle(request)
		
		self._log.info(
			"SyntacticValidationHandler: Unable to process request: %s. Passing it to next handler...",
			request.request_type
		)
		return super().handle(request)
