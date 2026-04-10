import csv
import traceback
from pathlib import Path
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import MetaData
from sqlmodel import Session

from session.db_session import DBSession


class FileIngestion:
	def __init__(self, config: dict, session: DBSession):
		self._config = config
		self._data_rows = []
		self._session = session
		self._db_table = None
		
		self._log = logging.getLogger("data_ontology")

	def ingest(self):
		self._log.info("File Ingestion: Starting ingestion for %s...", self._config["name"])
		self._load_dataset()
		self._upload_to_db()
	
	def _load_dataset(self):
		self._log.info("File Ingestion: Loading Dataset: %s", self._config["dataset"]["source"]["url"])
		
		file_path = Path.from_uri(self._config["dataset"]["source"]["url"])
		with open(file_path) as csvfile:
			csv_reader = csv.DictReader(
				csvfile,
				delimiter=self._config["dataset"]["source"]["delimiter"],
				quotechar=self._config["dataset"]["source"].get("quotechar", '"')
			)
			
			for row in csv_reader:
				self._data_rows.append(row)
	
	def _upload_to_db(self):
		metadata = MetaData(schema=None)
		metadata.reflect(
			bind=self._session.engine,
			only=[self._config["datasource"]["table"]["name"]],
			views=True
		)
		
		self._db_table = metadata.tables[self._config["datasource"]["table"]["name"]]
		
		with Session(self._session.engine) as session:
			try:
				self._log.info(
					"File Ingestion: Inserting data into: %s",
					self._config["datasource"]["table"]["name"]
				)
				statement = self._db_table.insert().values(self._data_rows)
				session.exec(statement)
				session.commit()
				
				self._log.info("File Ingestion: Data Ingestion completed for %s", self._config["name"])
			
			except SQLAlchemyError as e:
				self._log.error("File Ingestion: SQL Error occurred! %s", e)
				self._log.error(traceback.format_exc())
