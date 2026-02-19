import logging
import os
from pathlib import Path
import tomllib
import traceback


class BaseConfig:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")
        self._root = os.getenv('PROJECT_PATH', Path('home', 'default'))

    def _load_config(self, config_type: str):
        try:
            with open(Path(self._root, 'resources', 'config.toml')) as cf:
                data = cf.read()
                return tomllib.loads(data)[config_type]

        except FileNotFoundError as e:
            self._log.error("Config: Configuration file is not available")
            raise e

        except Exception as e:
            self._log.error("Config: Error Encountered when loading config file")
            self._log.error(e)
            self._log.error(traceback.format_exc())
