from ingestion.source.file_source.file_ingestion import FileIngestion
from session.db_session import DBSession
from sqlmodel import Session
from sqlalchemy import text


def test_file_ingestion(tmp_path, in_memory_engine):
    # create a simple csv file
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("col1,col2\n1,2\n3,4\n")

    config = {
        "name": "test",
        "dataset": {
            "source": {
                "url": csv_file.as_uri(),
                "delimiter": ",",
                "quotechar": '"',
            }
        },
        "datasource": {
            "driver": {"package": "drivers.sqlite_driver", "class": "SQLiteDriver", "options": {}},
            "database": {"name": "db", "connection_url": "sqlite:///:memory:", "options": {"echo": False}},
            "table": {"name": "some_table"},
        },
    }

    # prepare the target table manually
    session = DBSession(config)
    engine = session.engine
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE some_table (col1 TEXT, col2 TEXT)"))

    fi = FileIngestion(config, session)
    fi.ingest()

    # verify the rows were inserted
    with Session(engine) as s:
        rows = s.execute(text("SELECT * FROM some_table")).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "1"
        assert rows[1][1] == "4"
