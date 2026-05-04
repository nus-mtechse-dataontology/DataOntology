from types import ModuleType, SimpleNamespace

import pytest

import batch_main


def test_ingestion_api_initialises_typer_and_command():
    api = batch_main.IngestionAPI()

    assert api.app is not None
    assert api._ingestion_name == ""


def test_main_without_ingestion_type_exits():
    api = batch_main.IngestionAPI()

    with pytest.raises(SystemExit) as exc:
        api.main(ingestion_type="", project_path="C:/tmp")

    assert exc.value.code == 2


def test_main_wires_all_steps(tmp_path, monkeypatch):
    datasets = tmp_path / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    (datasets / "demo.yml").write_text(
        """
modules:
  entry:
    package: demo.entry
    class: DemoEntry
""".strip(),
        encoding="utf-8",
    )

    api = batch_main.IngestionAPI()

    calls = []

    class FakeEntry:
        def __init__(self, config, session):
            self.config = config
            self.session = session
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(batch_main, "DBSession", lambda config: SimpleNamespace(engine="engine-1"))
    monkeypatch.setattr(batch_main.SQLModel.metadata, "create_all", lambda engine: calls.append(("create_all", engine)))
    fake_module = ModuleType("demo.entry")
    setattr(fake_module, "DemoEntry", FakeEntry)
    monkeypatch.setattr(batch_main.im, "import_module", lambda package, name: fake_module)

    monkeypatch.setitem(__import__("sys").modules, "demo.entry", fake_module)

    api._root = str(tmp_path)
    api._ingestion_name = "demo"
    api._config = {"modules": {"entry": {"package": "demo.entry", "class": "DemoEntry"}}}
    api._get_session()
    api._create_or_load_tables()
    api._load_entry()
    api._run()

    assert api._session.engine == "engine-1"
    assert isinstance(api._entry, FakeEntry)
    assert api._entry.started is True
    assert calls == [("create_all", "engine-1")]
