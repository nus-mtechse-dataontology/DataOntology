import os
import importlib as im
import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Annotated
import traceback

import typer
import yaml
from sqlmodel import SQLModel

from configurations.logger_config import LoggerConfig
from entities import *
from ingestion.entry.base_entry import BaseEntry
from session.db_session import DBSession


class IngestionAPI:
	
	def __init__(self):
		self.app = typer.Typer()
		self._ingestion_name: str = ""
		self._root: str = ""
		self._config = {}
		self._entry: BaseEntry | None = None
		self._session: DBSession | None = None
		self._log = logging.getLogger("ingestion")
		self._add_command()
	
	def _add_command(self):
		self.app.command()(self.main)
	
	def main(
			self,
			ingestion_type: Annotated[str, typer.Option(help="Type of ingestion to run")] = "",
			project_path: Annotated[str, typer.Option(help="The working directory")] = ""
	):
		if ingestion_type == "":
			exit(2)
		else:
			os.environ["PROJECT_PATH"] = project_path
			self._root = project_path
			self._ingestion_name = ingestion_type
			self._load_config()
			self._get_session()
			self._create_or_load_tables()
			self._load_entry()
			self._run()
	
	def _run(self):
		self._entry.start()
	
	def _load_entry(self):
		"""
		Loads the entry class
		:return:
		"""
		entry = im.import_module(
			self._config["modules"]["entry"]["package"],
			self._config["modules"]["entry"]["package"]
		)
		entry_class = getattr(entry, self._config["modules"]["entry"]["class"])
		self._entry = entry_class(self._config, self._session)
	
	def _create_or_load_tables(self):
		SQLModel.metadata.create_all(self._session.engine)
	
	def _get_session(self):
		self._session = DBSession(self._config)
	
	def _load_config(self) -> None:
		"""
		Loads the config for the named ingestion.
		"""
		with open(Path(self._root, "datasets", f"{self._ingestion_name}.yml")) as cf:
			try:
				self._config = yaml.safe_load(cf)
			
			except yaml.YAMLError as exc:
				self._log.error("API Ingestion: error while loading config, %s", exc)
				self._log.error(traceback.format_exc())
				raise exc


if __name__ == "__main__":
	dictConfig(LoggerConfig().logger_config)
	IngestionAPI().app()
