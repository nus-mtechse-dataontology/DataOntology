from typing import Any

from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse


class SQLCompilerHandler(AbstractHandler):
	def __init__(self):
		super().__init__("SQLCompilerHandler")
	
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		...
