from ingestion.gateway.api_gateway import ApiGateway
from ingestion.source.api_source.city_api_ingestion import ApiIngestion
from ingestion.services.country_service import CountryService


class CountryApiIngestion(ApiIngestion):
	def __init__(self, api_gateway: ApiGateway, country_service: CountryService, config: dict):
		super().__init__(api_gateway, config)
		self._ingestion_name = "country"
		self._service = country_service
		
	def _upload_to_db(self, response_payload: dict):
		self._log.info("Country: Starting ingestion of Country data.. ")
		self._service.insert_countries(response_payload["data"]["destinationList"])
		self._log.info("Country: Finished ingestion of Country data.. ")
