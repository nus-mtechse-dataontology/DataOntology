"""Unit tests for Orchestrator — handler-chain wiring and delegation."""

from unittest.mock import Mock

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse
from src.orchestrator.orchestrator import Orchestrator

REQUEST_ID = "req-123"


def _make_handler():
    """Mock handler whose set_next returns its argument (enables real chaining)."""
    h = Mock()
    h.set_next = Mock(side_effect=lambda next_h: next_h)
    return h


def _build_orchestrator(request_handler=None, handle_return=None):
    """Build Orchestrator with mock handlers. request_handler.handle returns handle_return."""
    rh = request_handler or _make_handler()
    if handle_return is not None:
        rh.handle.return_value = handle_return
    return Orchestrator(
        request_handler=rh,
        prompt_handler=_make_handler(),
        llm_handler=_make_handler(),
        syntactic_validation_handler=_make_handler(),
        semantics_validation_handler=_make_handler(),
        sql_compiler_handler=_make_handler(),
        sql_executor_handler=_make_handler(),
        response_builder_handler=_make_handler(),
    ), rh


def _success(data=None):
    return SuccessResponse(
        request_id=REQUEST_ID,
        data=data or QuestionResponse(request_id=REQUEST_ID, response="ok"),
    )


def _error(component="stage"):
    return ErrorResponse(
        request_id=REQUEST_ID,
        error=ErrorDetails(code="stage_failed", message="failed", component=component),
    )


# ── delegation ────────────────────────────────────────────────────────────


def test_handle_question_delegates_to_request_handler():
    orchestrator, rh = _build_orchestrator(handle_return=_success())
    request = NLQRequest(request_id=REQUEST_ID, question="cheapest flight?")

    orchestrator.handle_question(request)

    rh.handle.assert_called_once_with(request)


def test_handle_question_returns_success_response_from_handler():
    expected = _success()
    orchestrator, _ = _build_orchestrator(handle_return=expected)

    result = orchestrator.handle_question(NLQRequest(request_id=REQUEST_ID, question="q"))

    assert result is expected
    assert isinstance(result, SuccessResponse)


def test_handle_question_returns_error_response_from_handler():
    expected = _error()
    orchestrator, _ = _build_orchestrator(handle_return=expected)

    result = orchestrator.handle_question(NLQRequest(request_id=REQUEST_ID, question="q"))

    assert result is expected
    assert isinstance(result, ErrorResponse)


# ── chain wiring ──────────────────────────────────────────────────────────


def test_chain_wired_in_correct_order():
    """Verify set_next is called on each handler in pipeline order."""
    handlers = {
        "request": _make_handler(),
        "prompt": _make_handler(),
        "llm": _make_handler(),
        "syntactic": _make_handler(),
        "semantics": _make_handler(),
        "sql_compiler": _make_handler(),
        "sql_executor": _make_handler(),
        "response_builder": _make_handler(),
    }
    handlers["request"].handle.return_value = _success()

    Orchestrator(
        request_handler=handlers["request"],
        prompt_handler=handlers["prompt"],
        llm_handler=handlers["llm"],
        syntactic_validation_handler=handlers["syntactic"],
        semantics_validation_handler=handlers["semantics"],
        sql_compiler_handler=handlers["sql_compiler"],
        sql_executor_handler=handlers["sql_executor"],
        response_builder_handler=handlers["response_builder"],
    )

    handlers["request"].set_next.assert_called_once_with(handlers["prompt"])
    handlers["prompt"].set_next.assert_called_once_with(handlers["llm"])
    handlers["llm"].set_next.assert_called_once_with(handlers["syntactic"])
    handlers["syntactic"].set_next.assert_called_once_with(handlers["semantics"])
    handlers["semantics"].set_next.assert_called_once_with(handlers["sql_compiler"])
    handlers["sql_compiler"].set_next.assert_called_once_with(handlers["sql_executor"])
    handlers["sql_executor"].set_next.assert_called_once_with(handlers["response_builder"])


def test_handle_question_calls_handler_exactly_once():
    orchestrator, rh = _build_orchestrator(handle_return=_success())

    orchestrator.handle_question(NLQRequest(question="q"))
    orchestrator.handle_question(NLQRequest(question="q2"))

    assert rh.handle.call_count == 2
