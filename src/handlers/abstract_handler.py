from models import ErrorDetails, NLQRequest
from models.common import SuccessResponse, ErrorResponse

from abc import abstractmethod
import json
import logging
import os
from pathlib import Path
from typing import Any

from handlers.handler import Handler


class AbstractHandler(Handler):
	def __init__(self, component_name: str):
		super().__init__()
		self._component_name = component_name
		self._semantics = {}
		self._log = logging.getLogger("data_ontology")
		self._root = os.getenv("PROJECT_PATH", "var/task")
		self._next_handler: Handler | None = None
	
	def set_next(self, handler: Handler) -> Handler:
		"""
		Sets the handler chain
		
		:param handler: The handler to set
		:return: The Handler
		"""
		self._next_handler = handler
		return handler
	
	def _load_semantics(self) -> None:
		"""
		Loads The semantics layer
		"""
		semantics_file = Path(self._root, "resources", "semantics", "semantic_layer_v2.json")
		
		try:
			with open(semantics_file) as jf:
				semantics_data = json.loads(jf.read())
				self._semantics = semantics_data
		
		except FileNotFoundError as e:
			self._log.error("Decorator: Failed to load semantics file at: %s", semantics_file)
			self._log.error(e)
			raise FileNotFoundError from e
	
	@abstractmethod
	def handle(self, request: NLQRequest) -> SuccessResponse | ErrorResponse:
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
				message=f"Reach end of responsibility chain. No handler to handle such request: {request.request_type}.",
				component=self._component_name
			)
		)
