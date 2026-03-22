from models.common import SuccessResponse, ErrorResponse

from abc import ABC, abstractmethod


class Handler(ABC):
	"""
	Handler interface that declares a method for building the chain of handlers and
	a method for executing a request
	"""
	def __init__(self):
		pass
	
	@abstractmethod
	def set_next(self, handler: Handler) -> Handler:
		pass
	
	@abstractmethod
	def handle(self, request) -> SuccessResponse | ErrorResponse:
		pass
