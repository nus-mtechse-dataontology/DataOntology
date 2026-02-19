from configurations.base_config import BaseConfig
from models.app_model import AppModel, ApiModel, AllowModel


class AppConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self._app_config: AppModel | None = None

    @property
    def app_config(self) -> AppModel | None:
        """
        Getter for Application Config
        """
        if self._app_config is None:
            self._get_config()

        return self._app_config

    @app_config.setter
    def app_config(self, config: AppModel):
        self._app_config = config

    def _get_config(self):
        """
        Gets the service configurations
        """
        self._log.info("App: Getting Application Configurations.. ")

        config = self._load_config('service')
        self.app_config = AppModel(
            host=config['host'],
            port=config['port'],
            reload=config['reload'],
            scheme=config['scheme'],
            api_endpoint=ApiModel(
                allow=AllowModel(
                    origins=config['allow_origins'],
                    credentials=config['credentials'],
                    methods=config['methods'],
                    headers=config['headers']
                ),
                redoc_url=config['redoc_url'],
                docs_url=config['docs_url'],
                root_path=config['root_path']
            ),
        )
