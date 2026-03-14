from logging.config import dictConfig
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from configurations.admin_config import AdminConfig
from configurations.app_config import AppConfig
from configurations.logger_config import LoggerConfig
from endpoints.routes.query.query_routes import query_router
from endpoints.routes.status.status_routes import status_router
from endpoints.routes.telegram.telegram_routes import telegram_router
from endpoints.routes.ingestion.ingestion_routes import ingestion_router
from lifecycle_hooks.startup import startup
from models.admin_model import AdminModel
from models.app_model import AppModel


class DataOntology:
    def __init__(self):
        self._app: FastAPI | None = None
        self._admin_config: AdminModel | None = None
        self._config: AppModel | None = None
        self._logger_config: dict[str, Any] | None = None

    def start(self):
        """
        Starting point for the app.
        1. Loads all configurations.
        2. Initialise the app with configurations loaded.
        """
        self._load_config()
        self._init_app()

        uvicorn.run(
            self._app,
            host=self._config.host,
            port=self._config.port,
            reload=self._config.reload,
            log_config=self._logger_config
        )

    def _load_config(self):
        self._admin_config = AdminConfig().admin_config
        self._config = AppConfig().app_config
        self._logger_config = LoggerConfig().logger_config
        dictConfig(self._logger_config)

    def _init_app(self):
        """
        Initialise and configures the FastAPI application
        """
        self._app = FastAPI(
            title="Data Ontology",
            docs_url=self._config.api_endpoint.docs_url,
            redoc_url=self._config.api_endpoint.redoc_url,
            root_path=self._config.api_endpoint.root_path,
            lifespan=startup
        )

        self._add_middleware()
        self._include_routers()

    def _add_middleware(self):
        self._app.add_middleware(TrustedHostMiddleware)
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=self._config.api_endpoint.allow.origins,
            allow_credentials=self._config.api_endpoint.allow.credentials,
            allow_methods=self._config.api_endpoint.allow.methods,
            allow_headers=self._config.api_endpoint.allow.headers,
        )

    def _include_routers(self):
        self._app.include_router(query_router)
        self._app.include_router(status_router)
        self._app.include_router(telegram_router)
        self._app.include_router(ingestion_router)


if __name__ == "__main__":
    DataOntology().start()
