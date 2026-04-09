from ingestion.gateway.api_gateway import ApiGateway
from ingestion.source.api_source.api_ingestion import ApiIngestion
from ingestion.services.airline_coverage_service import AirlineCoverageService


class AirlineCoverageApiIngestion(ApiIngestion):
	def __init__(
			self,
			api_gateway: ApiGateway,
			airline_coverage_service: AirlineCoverageService,
			config: dict
	):
		super().__init__(api_gateway, config)
		self._ingestion_name = "airline_coverage"
		self._service = airline_coverage_service
		
	def _upload_to_db(self, response_payload: dict):
		self._log.info("Airline Coverage: Starting ingestion of Airline Coverage data.. ")
		self._service.insert_coverages(response_payload["data"]["destinationList"])
		self._log.info("Airline Coverage: Ingestion Completed..")
	