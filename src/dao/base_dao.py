from abc import ABC
import logging
from typing import TypeVar

from sqlmodel import Session


T = TypeVar('T')


class BaseDAO[T](ABC):
	def __init__(self, engine):
		self._engine = engine
		self._log = logging.getLogger("ingestion")
	
	def insert_many(self, obj: list[T]) -> list[T]:
		self._log.info("BaseDAO: Inserting data into table...")
		with Session(self._engine) as session:
	
			session.add_all(obj)
			session.commit()

			for o in obj:
				session.refresh(o)

			return obj
