class DBExecutor:
    def execute(self, sql: str, params: list | None = None):
        raise NotImplementedError
