from types import SimpleNamespace

import main


def _fake_app_config():
    allow = SimpleNamespace(origins=["*"], credentials=True, methods=["*"], headers=["*"])
    api_endpoint = SimpleNamespace(
        allow=allow,
        redoc_url="/redoc",
        docs_url="/docs",
        root_path="/ontology",
    )
    return SimpleNamespace(host="0.0.0.0", port=8000, reload=False, api_endpoint=api_endpoint)


def test_load_config_reads_three_config_sources(monkeypatch):
    app_cfg = _fake_app_config()
    admin_cfg = SimpleNamespace(admin_host="127.0.0.1", admin_port=8080)
    logger_cfg = {"version": 1}

    class FakeAdminConfig:
        @property
        def admin_config(self):
            return admin_cfg

    class FakeAppConfig:
        @property
        def app_config(self):
            return app_cfg

    class FakeLoggerConfig:
        @property
        def logger_config(self):
            return logger_cfg

    calls = []
    monkeypatch.setattr(main, "AdminConfig", FakeAdminConfig)
    monkeypatch.setattr(main, "AppConfig", FakeAppConfig)
    monkeypatch.setattr(main, "LoggerConfig", FakeLoggerConfig)
    monkeypatch.setattr(main, "dictConfig", lambda cfg: calls.append(cfg))

    app = main.DataOntology()
    app._load_config()

    assert app._admin_config == admin_cfg
    assert app._config == app_cfg
    assert app._logger_config == logger_cfg
    assert calls == [logger_cfg]


def test_init_app_and_start(monkeypatch):
    app_cfg = _fake_app_config()

    started = {}
    monkeypatch.setattr(main, "startup", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: started.update(kwargs))

    app = main.DataOntology()
    app._config = app_cfg
    app._init_app()

    assert app._app is not None
    paths = {route.path for route in app._app.routes}
    assert "/actuator/health/liveness" in paths
    assert "/auth/login" in paths

    class FakeAdminConfig:
        @property
        def admin_config(self):
            return SimpleNamespace(admin_host="127.0.0.1", admin_port=8080)

    class FakeAppConfig:
        @property
        def app_config(self):
            return app_cfg

    class FakeLoggerConfig:
        @property
        def logger_config(self):
            return {"version": 1}

    monkeypatch.setattr(main, "AdminConfig", FakeAdminConfig)
    monkeypatch.setattr(main, "AppConfig", FakeAppConfig)
    monkeypatch.setattr(main, "LoggerConfig", FakeLoggerConfig)
    monkeypatch.setattr(main, "dictConfig", lambda cfg: None)

    app2 = main.DataOntology()
    app2.start()

    assert started["host"] == "0.0.0.0"
    assert started["port"] == 8000
    assert started["reload"] is False
