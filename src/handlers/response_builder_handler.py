from typing import Any

from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse


class ResponseBuilderHandler(AbstractHandler):
	def __init__(self):
		super().__init__("ResponseBuilderHandler")
	
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		...
