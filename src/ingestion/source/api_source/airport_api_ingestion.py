from ingestion.gateway.api_gateway import ApiGateway
from ingestion.source.api_source.api_ingestion import ApiIngestion
from ingestion.services.airport_service import AirportService


class AirportApiIngestion(ApiIngestion):
	def __init__(self, api_gateway: ApiGateway, airport_service: AirportService, config: dict) -> None:
		super().__init__(api_gateway, config)
		self._ingestion_name = "airport"
		self._service = airport_service
		
	def _upload_to_db(self, response_payload: dict):
		self._log.info("Airport: Starting ingestion of Airport data.. ")
		self._service.insert_airports(response_payload["data"]["destinationList"])
		self._log.info("Airport: Finished ingestion of Airport data.. ")
