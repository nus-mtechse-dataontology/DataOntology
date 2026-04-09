import logging
import os
import tomllib
import traceback
from pathlib import Path


class BaseConfig:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")
        env_project_path = os.getenv("PROJECT_PATH")
        if env_project_path:
            self._root = Path(env_project_path).expanduser().resolve()
        else:
            # src/configurations/base_config.py -> project root
            self._root = Path(__file__).resolve().parents[2]

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
