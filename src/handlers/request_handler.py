from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest
from uuid import uuid4


class RequestHandler(AbstractHandler):
	def __init__(self):
		super().__init__("RequestHandler")
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		"""
		Handles the 'request' request. Generates UUID4 for the NLQ Request.
		Passes request to the next handler down the chain if criteria not met for this handler.
		:param request: The NLQ Request
		:return: SuccessResponse or ErrorResponse
		"""
		request_id = str(uuid4())
		
		self._log.info("RequestHandler: Validating Request...")
		
		if request.request_type == "request":
			request.request_id = request_id
			request.request_type = "prompt"
		
		self._log.info("RequestHandler: NLQ Request validated, passing to the next handler...")
		return super().handle(request)
