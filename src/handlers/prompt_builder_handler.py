from typing import Any

from handlers.abstract_handler import AbstractHandler
from models import SuccessResponse, ErrorResponse


class PromptBuilderHandler(AbstractHandler):
	def __init__(self):
		super().__init__("PromptBuilderHandler")
	
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		...
