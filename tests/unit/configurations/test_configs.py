from configurations.admin_config import AdminConfig
from configurations.app_config import AppConfig
from configurations.logger_config import LoggerConfig


def _write_config_file(root, content: str):
    resources = root / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "config.toml").write_text(content, encoding="utf-8")


def test_app_admin_and_logger_configs_load_from_project_path(tmp_path, monkeypatch):
    _write_config_file(
        tmp_path,
        """
[logger]
version = 1

[service]
host = "0.0.0.0"
port = 8000
reload = false
scheme = "http"
allow_origins = ["*"]
credentials = true
methods = ["*"]
headers = ["*"]
redoc_url = "/redoc"
docs_url = "/docs"
root_path = "/ontology"

[admin]
admin_host = "127.0.0.1"
admin_port = 8080
context_path = "/admin/instances"
scheme = "http"
""".strip(),
    )
    monkeypatch.setenv("PROJECT_PATH", str(tmp_path))

    app_config = AppConfig().app_config
    admin_config = AdminConfig().admin_config
    logger_config = LoggerConfig().logger_config

    assert app_config.host == "0.0.0.0"
    assert app_config.port == 8000
    assert app_config.scheme == "http"
    assert app_config.api_endpoint.allow.origins == ["*"]
    assert app_config.api_endpoint.docs_url == "/docs"

    assert admin_config.admin_host == "127.0.0.1"
    assert admin_config.admin_port == 8080
    assert admin_config.context_path == "/admin/instances"

    assert logger_config["version"] == 1
