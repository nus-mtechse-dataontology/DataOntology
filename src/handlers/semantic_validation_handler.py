from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails
from validators import SemanticValidator


class SemanticsValidationHandler(AbstractHandler):
	def __init__(self, semantics_validation: SemanticValidator):
		super().__init__("SemanticsValidationHandler")
		self._semantics_validation = semantics_validation
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'semantics' request. Passes request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		if request.request_type == "semantics":
			self._log.info("SemanticsValidationHandler: Validating semantics response from LLM..")
			if request.query_plan is not None:
				self._load_semantics()
				validated_plan = self._semantics_validation.validate(request.query_plan, self._semantics)
				
				if isinstance(validated_plan, ErrorResponse):
					self._log.error("SemanticsValidationHandler: semantics is not valid...")
					self._log.error("SemanticsValidationHandler: Error: %s", validated_plan.error)
					return validated_plan
				
				self._log.info("SemanticsValidationHandler: Successfully validated semantics, passing to next handler...")
				request.request_type = "sql_compile"
				return super().handle(request)
				
				
			else:
				self._log.error("SemanticsValidationHandler: Error: Requires Semantics Validation Handler, but QueryPlan is None.")
				return ErrorResponse(
					request_id=request.request_id,
					error=ErrorDetails(
						code="SemanticsValidationHandlerError",
						message="Requires Semantics Validation Handler, but QueryPlan is None",
						component=self._component_name,
						details={
							"error": "Handler Error. Requesting for Semantics Validation Handler, but QueryPlan is None."
						}
					)
				)
		
		self._log.info(
			"SemanticsValidationHandler: Unable to process request: %s. Passing it to next handler...",
			request.request_type
		)
		return super().handle(request)
