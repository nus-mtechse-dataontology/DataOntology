from abc import ABC
import logging
from typing import TypeVar, Generic


T = TypeVar("T")


class DriverFactory[T](ABC):
	def __init__(self):
		self._log = logging.getLogger("data_ontology")
		
	@staticmethod
	def create_driver(self, package: str, class_name: str) -> T:
		"""
		Creates the driver object.
		"""
		pass
