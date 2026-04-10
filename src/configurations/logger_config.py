from typing import Any

from configurations.base_config import BaseConfig


class LoggerConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self._logger_config: dict[str, Any] | None = None

    @property
    def logger_config(self) -> dict[str, Any]:
        """
        Gets the logger configurations
        """
        if self._logger_config is None:
            self._logger_config = self._load_config("logger")
        return self._logger_config

    @logger_config.setter
    def logger_config(self, config: dict[str, Any]):
        """
        Sets the logger configurations
        """
        self._logger_config = config
