import logging

from entities.country import Country
from dao.country_dao import CountryDAO


class CountryService:
	def __init__(self, country_dao: CountryDAO):
		self._log = logging.getLogger("ontology")
		self._country_dao = country_dao
	
	def insert_countries(self, countries_payload: dict):
		countries = {}
		
		for country in countries_payload:
			countries[country["countryCode"]] = country["countryName"]
		
		self._country_dao.insert_many(
			[
				Country(
					f_country_code=key,
					f_country_name=value
				) for key, value in countries.items()
			]
		)
	
	def get_all_countries(self) -> list[Country]:
		return self._country_dao.get_all_countries()
