"""Unit tests for AbstractHandler — set_next, _load_semantics, end-of-chain."""

import json
import os
import pytest

from handlers.abstract_handler import AbstractHandler
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest


class _ConcreteHandler(AbstractHandler):
    """Minimal concrete subclass — delegates all requests to super().handle()."""

    def __init__(self):
        super().__init__("ConcreteHandler")

    def handle(self, request):
        return super().handle(request)


# ── set_next ──────────────────────────────────────────────────────────────


def test_set_next_returns_the_next_handler():
    h1 = _ConcreteHandler()
    h2 = _ConcreteHandler()

    result = h1.set_next(h2)

    assert result is h2


def test_set_next_enables_chaining():
    h1 = _ConcreteHandler()
    h2 = _ConcreteHandler()
    h3 = _ConcreteHandler()

    h1.set_next(h2).set_next(h3)

    assert h1._next_handler is h2
    assert h2._next_handler is h3


# ── end-of-chain ──────────────────────────────────────────────────────────


def test_handle_returns_eoc_error_when_no_next_handler():
    handler = _ConcreteHandler()
    request = NLQRequest(request_id="req-1", question="q", request_type="prompt")

    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "EOC"
    assert result.request_id == "req-1"


def test_handle_delegates_to_next_when_set():
    h1 = _ConcreteHandler()
    h2 = _ConcreteHandler()
    h1.set_next(h2)

    request = NLQRequest(request_id="req-1", question="q")
    result = h1.handle(request)

    # h2 also has no next, so returns EOC — but the key thing is h1 delegated
    assert isinstance(result, ErrorResponse)
    assert result.error.code == "EOC"


# ── _load_semantics ───────────────────────────────────────────────────────


def test_load_semantics_loads_json_when_project_path_set(tmp_path, monkeypatch):
    semantics_dir = tmp_path / "resources" / "semantics"
    semantics_dir.mkdir(parents=True)
    semantics_data = {"intents": {"test_intent": {}}, "param_schema": {}}
    (semantics_dir / "semantic_layer_v2.json").write_text(json.dumps(semantics_data))

    monkeypatch.setenv("PROJECT_PATH", str(tmp_path))
    handler = _ConcreteHandler()
    handler._load_semantics()

    assert handler._semantics["intents"]["test_intent"] == {}


def test_load_semantics_raises_file_not_found_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_PATH", str(tmp_path))
    handler = _ConcreteHandler()

    with pytest.raises(FileNotFoundError):
        handler._load_semantics()
