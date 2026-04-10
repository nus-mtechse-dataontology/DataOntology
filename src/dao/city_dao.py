from entities.city import City
from dao.base_dao import BaseDAO

from sqlmodel import Session, select


class CityDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)

	def get_all_cities(self) -> list[City]:
		with Session(self._engine) as session:
			cities = []
			statement = select(City)
			results = session.exec(statement)
			
			for city in results:
				cities.append(city)
			
			return cities
