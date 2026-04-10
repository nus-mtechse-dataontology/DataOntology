import logging

from entities.airport import Airport
from dao.airport_dao import AirportDAO


class AirportService:
	def __init__(self, airport_dao: AirportDAO):
		self._log = logging.getLogger("ontology")
		self._airport_dao = airport_dao
	
	def insert_airports(self, airport_payload: dict):
		airports = {}
		for airport in airport_payload:
			airports[airport["airportCode"]] = {
				"f_airport_code": airport["airportCode"],
				"f_airport_name": airport["airportName"],
				"f_city_code": airport["cityCode"]
			}
			
		self._airport_dao.insert_many([Airport(**airport) for key, airport in airports.items()])
	
	def get_all_airports(self) -> list[Airport]:
		return self._airport_dao.get_all_airports()
