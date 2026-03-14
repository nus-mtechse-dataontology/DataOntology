from abc import ABC, abstractmethod

from sqlalchemy import URL


class Driver(ABC):
	def __init__(self):
		self._connection_url: str | URL | None = None
	
	@abstractmethod
	def get_connection(self) -> str | URL:
		"""
		Create a new database connections.
		"""
		pass
