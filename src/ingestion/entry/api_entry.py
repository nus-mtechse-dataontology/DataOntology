from ingestion.entry.base_entry import BaseEntry
from ingestion.gateway.api_gateway import ApiGateway
from session.db_session import DBSession


class ApiEntry(BaseEntry):
	"""
	The API Entry class
	"""
	
	def __init__(self, config: dict, session: DBSession):
		super().__init__(config, session)
		self._api_gateway: ApiGateway | None = None
	
	def start(self):
		"""
		Entry point for the API Ingestion.
		:return:
		"""
		self._load_modules()
		self._ingestion.ingest()
	
	def _load_modules(self):
		"""
		Loads the modules required by the API Service.
		:return:
		"""
		self._api_gateway = (
			self._import_packages(
				self._config["modules"]["api_gateway"]["package"],
				self._config["modules"]["api_gateway"]["class"]
			)()
		)
		
		self._dao = (
			self._import_packages(
				self._config["modules"]["dao"]["package"],
				self._config["modules"]["dao"]["class"]
			)(self._session.engine)
		)
		
		self._service = (
			self._import_packages(
				self._config["modules"]["service"]["package"],
				self._config["modules"]["service"]["class"]
			)(self._dao)
		)
		
		self._ingestion = (
			self._import_packages(
				self._config["modules"]["ingestion"]["package"],
				self._config["modules"]["ingestion"]["class"]
			)(self._api_gateway, self._service, self._config)
		)
