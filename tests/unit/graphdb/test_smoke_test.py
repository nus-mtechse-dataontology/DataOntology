from types import ModuleType
import runpy
import sys


def test_smoke_test_runs_with_fake_graphdb_module(monkeypatch, capsys):
    fake_graphdb_pkg = ModuleType("graphdb")
    fake_graphdb_pkg.__path__ = []

    class FakeGraphDBService:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def graphdb_reachable(self):
            return True

        def ask(self, question):
            self.calls.append(question)
            return f"handled: {question}"

    fake_service_module = ModuleType("graphdb.service")
    fake_service_module.GraphDBService = FakeGraphDBService

    monkeypatch.setitem(sys.modules, "graphdb", fake_graphdb_pkg)
    monkeypatch.setitem(sys.modules, "graphdb.service", fake_service_module)

    runpy.run_path(str((__import__("pathlib").Path("src") / "graphdb" / "smoke_test.py").resolve()), run_name="__main__")

    output = capsys.readouterr().out
    assert "=== GraphDB Smoke Test ===" in output
    assert "OK" in output
    assert "REACHABLE" in output
    assert "handled:" in output
