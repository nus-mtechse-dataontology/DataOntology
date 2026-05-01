from entities.airport import Airport
from dao.base_dao import BaseDAO

from sqlmodel import Session, select


class FlightSearchDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
	
	def get_all_airports(self) -> list[Airport]:
		with Session(self._engine) as session:
			airports = []
			statement = select(Airport)
			results = session.exec(statement)
			
			for airport in results:
				airports.append(airport)
			
			return airports
