from drivers.driver import Driver
from factory.driver_factory import DriverFactory
import importlib as im


class DatabaseFactory(DriverFactory):
	def __init__(self):
		super().__init__()
	
	def create_driver(self, package: str, class_name: str) -> Driver:
		"""
		Creates the database driver object.
		
		:rtype: Driver
		:param package: Database Driver Package
		:param class_name: Database Driver Class
		:return: Database Driver Object
		"""
		self._log.info("Database Factory: Creating driver for: %s", class_name)
		
		driver = im.import_module(package, package)
		driver_class = getattr(driver, class_name)
		
		self._log.info("Database Factory: Driver: %s created.", class_name)
		return driver_class
