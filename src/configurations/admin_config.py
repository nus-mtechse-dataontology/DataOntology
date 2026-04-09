from configurations.base_config import BaseConfig
from models.admin_model import AdminModel


class AdminConfig(BaseConfig):
    def __init__(self):
        super().__init__()
        self._config: AdminModel | None = None

    @property
    def admin_config(self) -> AdminModel | None:
        """
        Gets the Admin Configurations
        """
        if self._config is None:
            self._get_config()

        return self._config

    @admin_config.setter
    def admin_config(self, config: AdminModel):
        """
        Sets the admin config
        """
        self._config = config

    def _get_config(self):
        """
        Gets the Admin Configurations
        """
        self._log.info("Admin: Getting Admin Configurations...")

        config = self._load_config("admin")
        self._config = AdminModel(
            admin_host=config['admin_host'],
            admin_port=config['admin_port'],
            context_path=config['context_path'],
            scheme=config['scheme']
        )
