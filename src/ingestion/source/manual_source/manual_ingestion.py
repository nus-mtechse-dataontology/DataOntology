import logging
import traceback

from sqlalchemy import delete
from sqlalchemy.schema import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from models.ingestion_model import IngestionModel
from session.db_session import DBSession


class ManualIngestion:
	def __init__(self, session: DBSession, payload: IngestionModel):
		self._db_table = None
		
		self._payload = payload
		self._session = session
		
		self._log = logging.getLogger("data_ontology")
		
	def ingest(self) -> dict[str, str | int]:
		self._get_table_metadata()
		status = self._upload_to_db()
		return status
		
	def _get_table_metadata(self):
		metadata = MetaData(schema=None)
		metadata.reflect(
			bind=self._session.engine,
			only=[self._payload.table_name],
			views=True
		)
		
		self._db_table = metadata.tables[self._payload.table_name]
		
	def _truncate_table(self) -> dict[str, str | int]:
		with Session(self._session.engine) as session:
			try:
				self._log.info(
					"Manual Ingestion: Truncating table: %s",
					self._payload.table_name
				)
				
				statement = delete(self._db_table)
				result = session.exec(statement)
				session.commit()
				
				return {
					'status_code': 0,
					'status': 'success',
					'records_truncated': result.rowcount
				}
			
			except SQLAlchemyError as e:
				self._log.error("Manual Ingestion: Error occurred when truncating %s...", e)
				self._log.error(traceback.format_exc())
				return {
					'status_code': 1,
					'status': 'error',
					'records_truncated': 0
				}
	
	def _upload_to_db(self) -> dict[str, str | int]:
		with Session(self._session.engine) as session:
			try:
				self._log.info(
					"Manual Ingestion: Inserting data into: %s",
					self._payload.table_name
				)
				statement = self._db_table.insert().values(self._payload.data)
				result = session.exec(statement)
				session.commit()
				
				self._log.info("Manual Ingestion: Data Ingestion completed for %s", self._payload.table_name)
				
				return {
					'status_code': 0,
					'status': 'success',
					'records_inserted': result.rowcount
				}
			
			except SQLAlchemyError as e:
				self._log.error("Manual Ingestion: SQL Error occurred! %s", e)
				self._log.error(traceback.format_exc())
				
				return {
					'status_code': 1,
					'status': 'error',
					'records_inserted': 0
				}
