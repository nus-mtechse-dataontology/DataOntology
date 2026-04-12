from orchestrator.response_builder import ResponseBuilder
from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest, ErrorDetails


class ResponseBuilderHandler(AbstractHandler):
	def __init__(self, response_builder: ResponseBuilder):
		super().__init__("ResponseBuilderHandler")
		self.response_builder = response_builder
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'result' request. Passes request to the next handler down the chain if criteria
        not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		if request.request_type == "result":
			self._log.info("ResponseBuilderHandler: Building Response...")
			if request.result_set is not None:
				return self.response_builder.build(request.result_set)
			
			else:
				self._log.error("ResponseBuilderHandler: Error: Requires Response Builder Handler, but ResultSet is None.")
				return ErrorResponse(
					request_id=request.request_id,
					error=ErrorDetails(
						code="ResponseBuilderHandlerError",
						message="Requires Response Builder Handler, but ResultSet is None.",
						component=self._component_name,
						details={
							"error": "Handler Error. Requesting for Response Builder Handler, but ResultSet is None."
						}
					)
				)
		
		self._log.info("ResponseBuilderHandler: Unable to process request: %s. Passing it to next handler...", request.request_type)
		return super().handle(request)
