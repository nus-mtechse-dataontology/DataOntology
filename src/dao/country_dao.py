from entities.country import Country
from dao.base_dao import BaseDAO

from sqlmodel import Session, select


class CountryDAO(BaseDAO):
	def __init__(self, engine):
		super().__init__(engine)
	
	def get_all_countries(self) -> list[Country]:
		with Session(self._engine) as session:
			countries = []
			statement = select(Country)
			results = session.exec(statement)
			
			for country in results:
				countries.append(country)
			
			return countries
			