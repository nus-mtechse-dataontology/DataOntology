from ingestion.gateway.api_gateway import ApiGateway
from ingestion.source.api_source.api_ingestion import ApiIngestion
from ingestion.services.flight_search_service import FlightSearchService


class FlightSearchApiIngestion(ApiIngestion):
	def __init__(self, api_gateway: ApiGateway, flight_search_service: FlightSearchService, config: dict) -> None:
		super().__init__(api_gateway, config)
		self._ingestion_name = "flight_search"
		self._service = flight_search_service
	
	def _upload_to_db(self, response_payload: dict):
		self._log.info("Flight Search: Starting ingestion of Flight Search data.. ")
		self._service.insert_flights(response_payload)
		self._log.info("Flight Search: Finished ingestion of Flight Search data.. ")
