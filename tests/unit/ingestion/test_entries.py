import importlib
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from ingestion.entry.base_entry import BaseEntry
from ingestion.entry.api_entry import ApiEntry


class DummyBaseEntry(BaseEntry):
    def start(self):
        return None

    def _load_modules(self):
        return None


def test_base_entry_import_packages_returns_class(monkeypatch):
    entry = DummyBaseEntry({}, Mock())
    mock_module = Mock()
    mock_class = Mock()
    setattr(mock_module, "SomeClass", mock_class)
    monkeypatch.setattr("ingestion.entry.base_entry.im.import_module", lambda package: mock_module)

    result = entry._import_packages("some.package", "SomeClass")

    assert result == mock_class


def test_api_entry_load_modules_and_start(monkeypatch):
    config = {
        "modules": {
            "api_gateway": {"package": "pkg.gateway", "class": "Gateway"},
            "dao": {"package": "pkg.dao", "class": "Dao"},
            "service": {"package": "pkg.service", "class": "Service"},
            "ingestion": {"package": "pkg.ingestion", "class": "Ingestion"},
        }
    }
    session = Mock()
    session.engine = object()
    entry = ApiEntry(config, session)

    class Gateway:
        pass

    class Dao:
        def __init__(self, engine):
            self.engine = engine

    class Service:
        def __init__(self, dao):
            self.dao = dao

    class Ingestion:
        def __init__(self, gateway, service, cfg):
            self.gateway = gateway
            self.service = service
            self.cfg = cfg
            self.ingested = False

        def ingest(self):
            self.ingested = True

    def fake_import(package, class_name):
        return {
            ("pkg.gateway", "Gateway"): Gateway,
            ("pkg.dao", "Dao"): Dao,
            ("pkg.service", "Service"): Service,
            ("pkg.ingestion", "Ingestion"): Ingestion,
        }[(package, class_name)]

    monkeypatch.setattr(entry, "_import_packages", fake_import)

    entry._load_modules()

    assert isinstance(entry._api_gateway, Gateway)
    assert isinstance(entry._dao, Dao)
    assert entry._dao.engine is session.engine
    assert isinstance(entry._service, Service)
    assert isinstance(entry._ingestion, Ingestion)
    assert entry._ingestion.cfg is config

    ingestion_mock = Mock()
    monkeypatch.setattr(entry, "_load_modules", lambda: setattr(entry, "_ingestion", ingestion_mock))
    entry.start()
    ingestion_mock.ingest.assert_called_once()


def test_file_entry_load_modules_and_start(monkeypatch):
    fake_session_pkg = ModuleType("ingestion.session")
    fake_session_pkg.__path__ = []
    fake_db_session_module = ModuleType("ingestion.session.db_session")
    fake_db_session_module.DBSession = object
    monkeypatch.setitem(sys.modules, "ingestion.session", fake_session_pkg)
    monkeypatch.setitem(sys.modules, "ingestion.session.db_session", fake_db_session_module)

    file_entry_module = importlib.import_module("ingestion.entry.file_entry")
    FileEntry = file_entry_module.FileEntry

    config = {
        "name": "demo",
        "modules": {
            "ingestion": {"package": "pkg.ingestion", "class": "Ingestion"},
        }
    }
    session = Mock()
    session.engine = object()
    entry = FileEntry(config, session)

    class Ingestion:
        def __init__(self, cfg, sess):
            self.cfg = cfg
            self.sess = sess
            self.ingested = False

        def ingest(self):
            self.ingested = True

    monkeypatch.setattr(entry, "_import_packages", lambda package, class_name: Ingestion)

    entry._load_modules()
    assert isinstance(entry._ingestion, Ingestion)
    assert entry._ingestion.cfg is config
    assert entry._ingestion.sess is session

    ingestion_mock = Mock()
    monkeypatch.setattr(entry, "_load_modules", lambda: setattr(entry, "_ingestion", ingestion_mock))
    entry.start()
    ingestion_mock.ingest.assert_called_once()
