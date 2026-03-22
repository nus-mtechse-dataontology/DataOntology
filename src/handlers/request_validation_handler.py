from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse, NLQRequest


class RequestValidationHandler(AbstractHandler):
	def __init__(self):
		super().__init__("RequestValidationHandler")
	
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
		...
