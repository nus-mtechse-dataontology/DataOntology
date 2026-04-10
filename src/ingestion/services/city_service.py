import logging

from entities.city import City
from dao.city_dao import CityDAO


class CityService:
	def __init__(self, city_dao: CityDAO):
		self._log = logging.getLogger("ontology")
		self._city_dao = city_dao
	
	def insert_cities(self, city_payload: dict):
		cities = {}
		for city in city_payload:
			cities[city["cityCode"]] = {
					"f_city_code": city["cityCode"],
					"f_city_name": city["cityName"],
					"f_country_code": city["countryCode"],
				}
		
		self._city_dao.insert_many([City(**city) for key, city in cities.items()])
	
	def get_all_cities(self) -> list[City]:
		return self._city_dao.get_all_cities()
