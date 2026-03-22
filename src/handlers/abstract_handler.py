from models import ErrorDetails
from models.common import SuccessResponse, ErrorResponse

from abc import abstractmethod
import logging
from typing import Any

from handlers.handler import Handler


class AbstractHandler(Handler):
	def __init__(self, component_name: str):
		super().__init__()
		self._component_name = component_name
		self._log = logging.getLogger("data_ontology")
		self._next_handler: Handler | None = None
	
	def set_next(self, handler: Handler) -> Handler:
		"""
		Sets the handler chain
		
		:param handler: The handler to set
		:return: The Handler
		"""
		self._next_handler = handler
		return handler
	
	@abstractmethod
	def handle(self, request: Any) -> SuccessResponse | ErrorResponse:
		"""
		Checks if there is other handler to handle the request, if not returns ErrorResponse.
		
		:param request: The client request
		:return: The SuccessResponse or ErrorResponse
		"""
		if self._next_handler:
			return self._next_handler.handle(request)
		
		return ErrorResponse(
			request_id=request.request_id,
			status="ERROR",
			error=ErrorDetails(
				code="EOC",
				message="Reach end of responsibility chain. No handler to handle such request.",
				component=self._component_name
			)
		)
