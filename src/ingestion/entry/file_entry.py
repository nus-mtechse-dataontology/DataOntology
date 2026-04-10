from ingestion.entry.base_entry import BaseEntry
from ingestion.session.db_session import DBSession


class FileEntry(BaseEntry):
	def __init__(self, config: dict, session: DBSession):
		super().__init__(config, session)
	
	def start(self):
		self._log.info("File Entry: Starting File Ingestion for %s", self._config["name"])
		self._load_modules()
		self._ingestion.ingest()
	
	def _load_modules(self):
		self._log.info("File Entry: Loading modules required for file ingestion...")
		
		self._ingestion = (
			self._import_packages(
				self._config["modules"]["ingestion"]["package"],
				self._config["modules"]["ingestion"]["class"]
			)(self._config, self._session)
		)
