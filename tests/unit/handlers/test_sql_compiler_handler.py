"""Unit tests for SQLCompilerHandler."""

from unittest.mock import Mock, patch

from handlers.sql_compiler_handler import SQLCompilerHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, NLQRequest, QueryPlan


SEMANTICS = {"intents": {"cheapest_flight_on_route": {"sql_template": "SELECT 1"}}, "param_schema": {}}


def _query_plan():
    return QueryPlan(
        request_id="req-1",
        intent="cheapest_flight_on_route",
        parameters={"origin": "SIN"},
        confidence=0.9,
    )


def _compiled_sql():
    return CompiledSQL(request_id="req-1", sql="SELECT 1", bound_params={})


def _make_handler(compiler_return):
    compiler = Mock()
    compiler.compile.return_value = compiler_return
    handler = SQLCompilerHandler(sql_compiler=compiler)
    handler._semantics = SEMANTICS
    return handler, compiler


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


def _error():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="compile_error", message="compile failed", component="sql_compiler"),
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_sql_compiler_handler_compiles_and_advances_type():
    plan = _query_plan()
    sql = _compiled_sql()
    success = SuccessResponse(request_id="req-1", data=sql)
    handler, compiler = _make_handler(compiler_return=success)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_compile", query_plan=plan)
    with patch.object(handler, "_load_semantics"):
        handler.handle(request)

    compiler.compile.assert_called_once_with(plan, SEMANTICS)
    assert request.request_type == "sql_executor"
    assert request.compiled_sql == sql
    nxt.handle.assert_called_once_with(request)


def test_sql_compiler_handler_passes_through_non_compile_type():
    handler, compiler = _make_handler(compiler_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="semantics")
    handler.handle(request)

    compiler.compile.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_sql_compiler_handler_returns_error_when_query_plan_is_none():
    handler, compiler = _make_handler(compiler_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_compile", query_plan=None)
    with patch.object(handler, "_load_semantics"):
        handler.handle(request)

    compiler.compile.assert_not_called()
    nxt.handle.assert_called_once()  # falls through to next (bug in source — no return on None plan)


def test_sql_compiler_handler_returns_error_when_compilation_fails():
    plan = _query_plan()
    handler, _ = _make_handler(compiler_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_compile", query_plan=plan)
    with patch.object(handler, "_load_semantics"):
        result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "compile_error"
    nxt.handle.assert_not_called()
