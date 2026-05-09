import logging
from dao.ingestion_dao import IngestionDAO
from models.ingestion_model import IngestionModel


class IngestionService:
	def __init__(self, ingestion_dao: IngestionDAO):
		self._ingestion_dao = ingestion_dao
		self._log = logging.getLogger("data_ontology")
	
	def upload_to_db(self, payload: IngestionModel) -> dict[str, int | str]:
		self._log.info("Ingestion Service: Uploading table data for: %s", payload.table_name)
		return self._ingestion_dao.upload_to_db(payload)
	
	def truncate_table(self, table_name: str) -> dict[str, str | int]:
		self._log.info("Ingestion Service: Truncating table data for: %s", table_name)
		return self._ingestion_dao.truncate_table(table_name)
	
	def get_table_data(self, table_name: str) -> dict[str, int | str]:
		self._log.info("Ingestion Service: Getting table data for: %s", table_name)
		return self._ingestion_dao.get_table_data(table_name)
	
	def get_schema_from_db(self) -> list[dict[str, str | bool | None]]:
		self._log.info("Ingestion Service: Getting Database Schema..")
		return self._ingestion_dao.get_schema_from_db()
