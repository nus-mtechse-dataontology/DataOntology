from abc import ABC, abstractmethod
import logging


class Session(ABC):
	def __init__(self):
		self._log = logging.getLogger("data_ontology")
	
	@abstractmethod
	def create_session(self):
		pass
