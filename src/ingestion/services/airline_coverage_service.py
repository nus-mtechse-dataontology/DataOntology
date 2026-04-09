import logging

from entities.airline_coverage import AirlineCoverage
from dao.airline_coverage_dao import AirlineCoverageDAO


class AirlineCoverageService:
	def __init__(self, airline_coverage_dao: AirlineCoverageDAO):
		self._log = logging.getLogger("ontology")
		self._airline_coverage_dao = airline_coverage_dao
		
	def insert_coverages(self, coverage_payload: dict):
		coverages_map = {}
		airline_coverages = []
		
		for airport in coverage_payload:
			if airport['airportCode'] != "SIN":
				coverages_map[airport['airportCode']] = [
					{
						"f_airport_code": airport['airportCode'],
						"f_airline_code": "SQ",
						"f_coverage": True if airport["isSQGtwyFlg"] else False
					},
					{
						"f_airport_code": airport['airportCode'],
						"f_airline_code": "TR",
						"f_coverage": True if airport["isTRDestination"] else False
					}
				]
				
		for ap_code, coverages in coverages_map.items():
			for coverage in coverages:
				airline_coverages.append(AirlineCoverage(**coverage))
				
		self._airline_coverage_dao.insert_many(airline_coverages)
