import logging

from ontology.execution.db import get_connection


class DBExecutor:
    def __init__(self):
        self._log = logging.getLogger("data_ontology")

    def run_query(self, db_path: str, sql: str, params: dict):
        conn = get_connection(db_path)
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
