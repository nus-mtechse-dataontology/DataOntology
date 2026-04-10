from dao.base_dao import BaseDAO

from typing import Sequence, Annotated, Any

from sqlalchemy import RowMapping
from sqlmodel import Session, text


class FactFlightInfoDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
	
	def execute_raw_query(
			self,
			query: str,
			params: dict[str, Any] | None = None
	) -> Annotated[list[dict[str, Any]], Sequence[RowMapping]]:
		"""
		Executes Raw SQL query and returns list of result in key, value pair.
		
		:param query: The raw query to execute
		:param params: Additional query parameters
		:return: The list of results
		"""
		with Session(self._engine) as session:
			stmt = text(query)
			result = session.exec(stmt, params=params)
			
			return result.mappings().all()
