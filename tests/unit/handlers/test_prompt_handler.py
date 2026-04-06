"""Unit tests for PromptHandler."""

import os
from unittest.mock import MagicMock, Mock, patch

from handlers.prompt_handler import PromptHandler
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, PromptBundle


SEMANTICS = {
    "intents": {"cheapest_flight_on_route": {"required_params": ["origin"]}},
    "param_schema": {"origin": {"type": "string"}},
}


def _make_handler(prompt_builder=None):
    builder = prompt_builder or Mock()
    handler = PromptHandler(prompt_builder=builder)
    handler._semantics = SEMANTICS
    handler._root = os.getcwd()
    return handler, builder


def _make_next(return_value=None):
    nxt = Mock()
    nxt.handle.return_value = return_value or SuccessResponse(
        request_id="req-1", data="ok"
    )
    return nxt


# ── happy path ────────────────────────────────────────────────────────────


def test_prompt_handler_calls_prompt_builder_and_advances_type():
    bundle = PromptBundle(system_message="sys", user_message="user")
    builder = Mock()
    builder.set_prompt_template.return_value = builder
    builder.set_question.return_value = builder
    builder.set_intent.return_value = builder
    builder.set_param_schema.return_value = builder
    builder.build.return_value = bundle

    handler, _ = _make_handler(prompt_builder=builder)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="cheapest flight?", request_type="prompt")

    with patch.object(handler, "_load_prompt", return_value="template"):
        handler.handle(request)

    assert request.request_type == "llm"
    assert request.system_message == bundle.system_message
    assert request.user_message == bundle.user_message
    nxt.handle.assert_called_once_with(request)


def test_prompt_handler_passes_through_non_prompt_type():
    handler, _ = _make_handler()
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="q", request_type="llm")
    handler.handle(request)

    assert request.request_type == "llm"
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_prompt_handler_returns_error_when_builder_raises():
    builder = Mock()
    builder.set_prompt_template.return_value = builder
    builder.set_question.return_value = builder
    builder.set_intent.return_value = builder
    builder.set_param_schema.return_value = builder
    builder.build.side_effect = KeyError("missing_field")

    handler, _ = _make_handler(prompt_builder=builder)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", question="q", request_type="prompt")

    with patch.object(handler, "_load_prompt", return_value="template"):
        result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-1"
    nxt.handle.assert_not_called()
