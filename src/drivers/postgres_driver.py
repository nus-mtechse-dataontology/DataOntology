import os
from pathlib import Path

from sqlalchemy import URL

from drivers.driver import Driver


class PostgresDriver(Driver):
	def __init__(self, config: dict):
		super().__init__()
		self._config = config
		self._root = os.getenv("PROJECT_PATH", os.getcwd())
	
	def get_connection(self) -> str | URL:
		"""
		Constructs a PostgreSQL connection
		:return: The connection URL
		"""
		if self._connection_url is None:
			self._connection_url = URL.create(
				self._config["datasource"]["database"]["drivername"],
				self._get_vault(self._config["datasource"]["database"]["options"]["user"]),
				self._get_vault(self._config["datasource"]["database"]["options"]["password"]),
				self._config["datasource"]["database"]["host"],
				self._config["datasource"]["database"]["port"],
				self._config["datasource"]["database"]["name"],
			)
		
		return self._connection_url
	
	def _get_vault(self, vault_name: str) -> str:
		"""
		Loads the vault file
		:param vault_name: Name of vault file
		:return: vault value
		"""
		with open(Path(self._root, "vault", vault_name)) as vf:
			return vf.read()
