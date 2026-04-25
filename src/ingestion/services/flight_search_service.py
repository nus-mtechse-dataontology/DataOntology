import logging
import json

from dao.flight_search_dao import FlightSearchDAO


class FlightSearchService:
	def __init__(self, flight_search_dao: FlightSearchDAO):
		self._log = logging.getLogger("data_ontology")
		self._flight_search_dao = flight_search_dao
	
	def insert_flights(self, flights: dict):
		self._log.info("Flights... %s", json.dumps(flights, indent=4))
