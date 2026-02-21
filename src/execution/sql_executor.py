"""Execute compiled SQL against the configured database."""

from models.pipeline import CompiledSQL, ResultSet


class SQLExecutor:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def execute(self, compiled_sql: CompiledSQL) -> ResultSet:
        del compiled_sql
        raise NotImplementedError("SQLExecutor.execute is not implemented yet.")
