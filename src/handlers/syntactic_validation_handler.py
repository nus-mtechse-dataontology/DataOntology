from typing import Any

from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse


class SyntacticValidationHandler(AbstractHandler):
	def __init__(self):
		super().__init__("SyntacticValidationHandler")
	
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		...
