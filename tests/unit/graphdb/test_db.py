from types import SimpleNamespace
from unittest.mock import Mock

from graphdb import db


def test_load_config_reads_config_file(tmp_path, monkeypatch):
    config_file = tmp_path / "resources" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        """
[datasource]
[datasource.database]
name = "demo"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(db, "_project_root", str(tmp_path))

    result = db._load_config()

    assert result["datasource"]["database"]["name"] == "demo"


def test_get_dao_caches_and_execute_sql(monkeypatch):
    db._dao = None
    monkeypatch.setattr(db, "_load_config", lambda: {"datasource": {"database": {}}})

    session_instance = SimpleNamespace(engine="engine-1")
    session_ctor = Mock(return_value=session_instance)
    dao_instance = Mock()
    dao_instance.execute_raw_query.return_value = [{"a": 1}, {"a": 2}]
    dao_ctor = Mock(return_value=dao_instance)

    monkeypatch.setattr(db, "DBSession", session_ctor)
    monkeypatch.setattr(db, "FactFlightInfoDAO", dao_ctor)

    dao1 = db._get_dao()
    dao2 = db._get_dao()
    rows = db.execute_sql("select 1", {"x": 1})

    assert dao1 is dao2
    session_ctor.assert_called_once()
    dao_ctor.assert_called_once_with("engine-1")
    dao_instance.execute_raw_query.assert_called_once_with("select 1", {"x": 1})
    assert rows == [{"a": 1}, {"a": 2}]
