"""Unit tests for SQLExecutorHandler."""

from unittest.mock import Mock

from handlers.sql_executor_handler import SQLExecutorHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, NLQRequest, ResultSet, Row


def _compiled_sql():
    return CompiledSQL(request_id="req-1", sql="SELECT 1", bound_params={})


def _result_set():
    return ResultSet(request_id="req-1", result_set=[Row(data={"fare": 100})])


def _make_handler(executor_return):
    executor = Mock()
    executor.execute.return_value = executor_return
    return SQLExecutorHandler(sql_executor=executor), executor


def _make_next():
    nxt = Mock()
    nxt.handle.return_value = SuccessResponse(request_id="req-1", data="ok")
    return nxt


def _error():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(code="db_error", message="db failed", component="sql_executor"),
    )


# ── happy path ────────────────────────────────────────────────────────────


def test_sql_executor_handler_executes_and_advances_type():
    rs = _result_set()
    success = SuccessResponse(request_id="req-1", data=rs)
    handler, executor = _make_handler(executor_return=success)
    nxt = _make_next()
    handler.set_next(nxt)

    sql = _compiled_sql()
    request = NLQRequest(request_id="req-1", request_type="sql_executor", compiled_sql=sql)
    handler.handle(request)

    executor.execute.assert_called_once_with(sql)
    assert request.request_type == "result"
    assert request.result_set == rs
    nxt.handle.assert_called_once_with(request)


def test_sql_executor_handler_passes_through_non_executor_type():
    handler, executor = _make_handler(executor_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_compile")
    handler.handle(request)

    executor.execute.assert_not_called()
    nxt.handle.assert_called_once_with(request)


# ── error cases ───────────────────────────────────────────────────────────


def test_sql_executor_handler_returns_error_when_compiled_sql_is_none():
    handler, executor = _make_handler(executor_return=None)
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_executor", compiled_sql=None)
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    executor.execute.assert_not_called()
    nxt.handle.assert_not_called()


def test_sql_executor_handler_returns_error_when_execution_fails():
    handler, _ = _make_handler(executor_return=_error())
    nxt = _make_next()
    handler.set_next(nxt)

    request = NLQRequest(request_id="req-1", request_type="sql_executor", compiled_sql=_compiled_sql())
    result = handler.handle(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "db_error"
    nxt.handle.assert_not_called()
