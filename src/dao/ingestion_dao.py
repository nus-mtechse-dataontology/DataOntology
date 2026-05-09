from dao.base_dao import BaseDAO
from models.ingestion_model import IngestionModel

import json
import logging
import traceback
from typing import TypeVar

from sqlalchemy import delete, inspect
from sqlalchemy.schema import MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

T = TypeVar('T')


class IngestionDAO(BaseDAO):
	def __init__(self, engine) -> None:
		super().__init__(engine)
		self._db_table = None
		self._table_name = ""
		self._log = logging.getLogger("data_ontology")
	
	def insert_many(self, obj: list[T]) -> dict[str, int | str]:
		with Session(self._engine) as session:
			try:
				self._log.info(
					"IngestionDAO: Inserting data into: %s...",
					self._db_table
				)
				statement = self._db_table.insert().values(obj)
				result = session.exec(statement)
				session.commit()
				
				self._log.info("IngestionDAO: Data Ingestion completed for %s", self._table_name)
				
				return {
					'status_code': 0,
					'status': 'success',
					'records_inserted': result.rowcount
				}
			
			except SQLAlchemyError as e:
				self._log.error("IngestionDAO: SQL Error occurred! %s", e)
				self._log.error(traceback.format_exc())
				
				return {
					'status_code': 1,
					'status': 'error',
					'records_inserted': 0
				}
	
	def upload_to_db(self, payload: IngestionModel) -> dict[str, int | str]:
		self._table_name = payload.table_name
		self._reflect_metadata()
		
		if payload.truncate:
			self.truncate_table(self._table_name)
		
		return self.insert_many(payload.data)
	
	def truncate_table(self, table_name: str) -> dict[str, int | str]:
		self._table_name = table_name
		self._reflect_metadata()
		
		with Session(self._engine) as session:
			try:
				self._log.info(
					"IngestionDAO: Truncating table: %s",
					self._table_name
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
				self._log.error("IngestionDAO: Error occurred when truncating %s...", e)
				self._log.error(traceback.format_exc())
				return {
					'status_code': 1,
					'status': 'error',
					'records_truncated': 0
				}
	
	def get_table_data(self, table_name: str) -> dict[str, int | str]:
		self._log.info("IngestionDAO: Getting Data for: %s", table_name)
		
		self._table_name = table_name
		self._reflect_metadata()
		
		statement = self._db_table.select()
		with Session(self._engine) as session:
			results = session.exec(statement)
			rows = [dict(r) for r in results.mappings().all()]
			return json.loads(json.dumps(rows, default=str))
		
	def get_schema_from_db(self) -> list[dict[str, str | bool | None]]:
		self._log.info("IngestionDAO: Getting Database Schema...")
		
		inspector = inspect(self._engine)
		tables = inspector.get_table_names()
		
		table_lists = []
		
		for table in tables:
			if table == "dim_accounts":
				continue
			
			table_schema = {
				"name": table,
				"description": "",
				"cols": []
			}
			for col in inspector.get_columns(table):
				if not col["autoincrement"]:
					table_schema["cols"].append(
						{
							"name": col["name"],
							"type": str(col["type"]),
							"nullable": col["nullable"],
							"default": col["default"],
							"autoincrement": col["autoincrement"],
							"comment": col["comment"]
						}
					)
				else:
					continue
			
			table_lists.append(table_schema)
		
		return table_lists
		
	def _reflect_metadata(self):
		metadata = MetaData(schema=None)
		metadata.reflect(
			bind=self._engine,
			only=[self._table_name],
			views=True
		)
		
		self._db_table = metadata.tables[self._table_name]
