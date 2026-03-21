"""Seam integration: Orchestrator with real SQLExecutor + temp SQLite database.

All other stages are mocked. Tests that CompiledSQL produced upstream is
correctly executed against a real database by the SQLExecutor, and that
the orchestrator handles success (with rows), empty results, and DB errors.
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

from execution.sql_executor import SQLExecutor
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import (
    CompiledSQL,
    LLMRawResponse,
    NLQRequest,
    PromptBundle,
    QueryPlan,
    ResultSet,
)
from orchestrator.error_response_builder import ErrorResponseBuilder
from orchestrator.orchestrator import Orchestrator
from orchestrator.response_builder import ResponseBuilder

import pytest

# ── helpers ──────────────────────────────────────────────────────────────

REQUEST_ID = "req-seam-exec-1"
NOW = "2026-02-24T22:00:00Z"


def _create_test_db(db_path: str) -> None:
    """Create a test SQLite database with flight-related tables and seed data."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE airport (
            airport_code TEXT PRIMARY KEY,
            city_name TEXT,
            country_name TEXT
        );

        INSERT INTO airport VALUES ('SIN', 'Singapore', 'Singapore');
        INSERT INTO airport VALUES ('BKK', 'Bangkok', 'Thailand');
        INSERT INTO airport VALUES ('NRT', 'Tokyo', 'Japan');

        CREATE TABLE flights (
            flight_id INTEGER PRIMARY KEY,
            origin TEXT,
            destination TEXT,
            departure_date TEXT,
            price REAL
        );

        INSERT INTO flights VALUES (1, 'SIN', 'BKK', '2019-09-01', 180.0);
        INSERT INTO flights VALUES (2, 'SIN', 'BKK', '2019-09-15', 210.0);
        INSERT INTO flights VALUES (3, 'SIN', 'NRT', '2019-09-01', 450.0);
        INSERT INTO flights VALUES (4, 'BKK', 'SIN', '2019-09-10', 175.0);
    """)
    conn.commit()
    conn.close()


def _build_orchestrator(
    *,
    db_path: str,
    compiled_sql: CompiledSQL,
) -> Orchestrator:
    """Build an Orchestrator with a real SQLExecutor, everything else mocked."""

    sql_executor = SQLExecutor(db_path)

    # Upstream mocks all succeed and pass the compiled_sql to sql_executor
    default_plan = QueryPlan(
        request_id=REQUEST_ID,
        intent="test_intent",
        parameters={},
        confidence=0.95,
    )

    return Orchestrator(
        semantic_model_provider=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data={"intents": {}})
        ),
        prompt_builder=Mock(
            return_value=SuccessResponse(
                request_id=REQUEST_ID,
                data=PromptBundle(
                    request_id=REQUEST_ID,
                    system_message="system",
                    user_message="user",
                ),
            )
        ),
        llm_gateway=Mock(
            return_value=SuccessResponse(
                request_id=REQUEST_ID,
                data=LLMRawResponse(request_id=REQUEST_ID, raw_response_text="{}"),
            )
        ),
        syntactic_validator=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_plan)
        ),
        semantic_validator=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=default_plan)
        ),
        sql_compiler=Mock(
            return_value=SuccessResponse(request_id=REQUEST_ID, data=compiled_sql)
        ),
        sql_executor=sql_executor.execute,
        response_builder=ResponseBuilder().build,
        error_response_builder=ErrorResponseBuilder().build,
        now_provider=lambda: NOW,
    )


# ── tests ────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_valid_sql_returns_matching_rows():
    """SQLExecutor executes parameterized SQL and returns matching rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        _create_test_db(db_path)

        compiled = CompiledSQL(
            request_id=REQUEST_ID,
            sql="SELECT origin, destination, price FROM flights "
                "WHERE origin = :origin AND destination = :destination "
                "ORDER BY price ASC LIMIT :limit",
            bound_params={"origin": "SIN", "destination": "BKK", "limit": 10},
        )
        orchestrator = _build_orchestrator(db_path=db_path, compiled_sql=compiled)

        request = NLQRequest(request_id=REQUEST_ID, question="Flights from SIN to BKK?")
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "2 matching records" in result.data.response
        assert "180.0" in result.data.response
        assert "210.0" in result.data.response


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_query_with_no_matching_rows_returns_no_records_message():
    """SQLExecutor returns empty ResultSet when no rows match the query."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        _create_test_db(db_path)

        compiled = CompiledSQL(
            request_id=REQUEST_ID,
            sql="SELECT * FROM flights WHERE origin = :origin LIMIT :limit",
            bound_params={"origin": "LAX", "limit": 10},  # LAX doesn't exist
        )
        orchestrator = _build_orchestrator(db_path=db_path, compiled_sql=compiled)

        request = NLQRequest(request_id=REQUEST_ID, question="Flights from LAX?")
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "could not find any matching records" in result.data.response


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_nonexistent_table_returns_execution_error():
    """SQL referencing a non-existent table → execution_error from SQLExecutor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        _create_test_db(db_path)

        compiled = CompiledSQL(
            request_id=REQUEST_ID,
            sql="SELECT * FROM nonexistent_table LIMIT :limit",
            bound_params={"limit": 10},
        )
        orchestrator = _build_orchestrator(db_path=db_path, compiled_sql=compiled)

        request = NLQRequest(request_id=REQUEST_ID, question="Bad table query")
        result = orchestrator.handle_question(request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "execution_error"
        assert result.error.component == "sql_executor"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_nonexistent_database_returns_connection_error():
    """SQLExecutor can't connect to non-existent database → connection_error."""
    compiled = CompiledSQL(
        request_id=REQUEST_ID,
        sql="SELECT 1",
        bound_params={},
    )
    orchestrator = _build_orchestrator(
        db_path="/nonexistent/path/to/database.db",
        compiled_sql=compiled,
    )

    request = NLQRequest(request_id=REQUEST_ID, question="Test query")
    result = orchestrator.handle_question(request)

    assert isinstance(result, ErrorResponse)
    assert result.error.component == "sql_executor"


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_single_row_result_produces_correct_response():
    """Single-row result formats correctly through ResponseBuilder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        _create_test_db(db_path)

        compiled = CompiledSQL(
            request_id=REQUEST_ID,
            sql="SELECT city_name, country_name FROM airport "
                "WHERE airport_code = :code LIMIT :limit",
            bound_params={"code": "SIN", "limit": 10},
        )
        orchestrator = _build_orchestrator(db_path=db_path, compiled_sql=compiled)

        request = NLQRequest(request_id=REQUEST_ID, question="What city is SIN?")
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "1 matching record" in result.data.response
        assert "Singapore" in result.data.response


@pytest.mark.skip(reason="Test need to updated due to change from sqlite to postgres")
def test_limit_parameter_restricts_row_count():
    """LIMIT in SQL restricts the number of rows returned."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        _create_test_db(db_path)

        compiled = CompiledSQL(
            request_id=REQUEST_ID,
            sql="SELECT * FROM flights ORDER BY price ASC LIMIT :limit",
            bound_params={"limit": 2},  # only 2 of 4 rows
        )
        orchestrator = _build_orchestrator(db_path=db_path, compiled_sql=compiled)

        request = NLQRequest(request_id=REQUEST_ID, question="Top 2 cheapest flights")
        result = orchestrator.handle_question(request)

        assert isinstance(result, SuccessResponse)
        assert "2 matching records" in result.data.response
