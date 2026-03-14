from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from factory.database_factory import DatabaseFactory


class DBSession:
	def __init__(self, config: dict):
		self._engine: Engine | None = None
		self._connection_url: str | None = None
		self._config: dict = config
	
	@property
	def engine(self) -> Engine | None:
		"""
		Returns the database engine. If the engine is not created yet, it creates a new one.
		:return: The database engine.
		"""
		if self._engine is None:
			self._get_connection()
			self._engine = create_engine(
				self._connection_url,
				echo=self._config["datasource"]["database"]["options"]["echo"]
			)
		
		return self._engine
		
	@engine.setter
	def engine(self, db_engine: Engine | None) -> None:
		"""
		Sets the database engine. This method can be used to set a custom database engine.
		:param db_engine: The database engine to set.
		"""
		self._engine = db_engine
	
	def _get_connection(self) -> None:
		"""
		Loads the database driver and creates a connection URL.
		"""
		driver = DatabaseFactory().create_driver(
			self._config["datasource"]["driver"]["package"],
			self._config["datasource"]["driver"]["class"]
		)
		
		self._connection_url = driver(self._config).get_connection()
