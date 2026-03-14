from abc import ABC, abstractmethod
import importlib as im
import logging
from typing import TypeVar

from dao.base_dao import BaseDAO
from ingestion.session.db_session import DBSession

T = TypeVar("T")


class BaseEntry[T](ABC):
	"""
	Base Entry class
	"""
	
	def __init__(self, config: dict, session: DBSession):
		self._config = config
		self._session = session
		
		self._dao: BaseDAO | None = None
		self._service: T | None = None
		self._ingestion: T | None = None
		
		self._log = logging.getLogger("ingestion")
	
	@abstractmethod
	def start(self):
		"""
		Entry point for the Ingestion.
		"""
		pass
	
	@abstractmethod
	def _load_modules(self):
		pass
	
	def _import_packages(self, package: str, class_name: str):
		"""
		Imports the module required by the Ingestion Service.
		:param package: The package to import
		:param class_name: The class name of the package
		:return: The imported module
		"""
		self._log.info("Entry: Importing package %s", package)
		module = im.import_module(package)
		module_class = getattr(module, class_name)
		
		return module_class
