from session.db_session import DBSession


def test_db_session_creates_engine(tmp_path):
    # use a memory database for simplicity
    config = {
        "datasource": {
            "driver": {"package": "drivers.sqlite_driver", "class": "SQLiteDriver", "options": {}},
            "database": {"name": "db", "connection_url": "sqlite:///:memory:", "options": {"echo": False}},
        }
    }

    dbs = DBSession(config)
    engine1 = dbs.engine
    assert engine1 is not None
    # repeated access returns same object
    assert dbs.engine is engine1
