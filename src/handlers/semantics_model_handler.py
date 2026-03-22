from typing import Any

from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse


class SemanticsModelHandler(AbstractHandler):
	def __init__(self):
		super().__init__("SemanticsModelHandler")
	
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		...
