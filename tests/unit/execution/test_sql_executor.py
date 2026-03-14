"""
Comprehensive tests for SQL Executor.

This test suite validates that the SQLExecutor correctly executes compiled SQL
against a database and returns structured results. Tests are organized by acceptance criteria:
1. SQL Executor establishes connection with database
2. SQL Executor executes SQL query against database
3. SQL Executor returns result set with Row objects
4. SQL Executor returns meaningful response when connection fails
5. SQL Executor returns meaningful response when querying fails
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

from execution.sql_executor import SQLExecutor
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, ResultSet, Row


# ==============================================================================
# FIXTURES - Test database and reusable test data
# ==============================================================================

@pytest.fixture
def test_db_path(tmp_path: Path) -> str:
    """
    Create a temporary SQLite database with test data.
    
    This fixture sets up a test database with sample flight data that mimics
    the production schema. The database is created fresh for each test and
    automatically cleaned up after the test completes.
    
    Schema:
    - search_response: Contains search metadata and currency info
    - recommendation: Contains pricing information for flights
    - flight: Contains flight route information
    - airport: Contains airport details
    
    Returns:
        str: Path to the temporary database file
    """
    db_file = tmp_path / "test_flights.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    
    # Create tables matching the production schema
    cursor.execute("""
        CREATE TABLE search_response (
            payload_id TEXT PRIMARY KEY,
            session_id TEXT,
            trip_type TEXT,
            currency_code TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE recommendation (
            payload_id TEXT,
            recommendation_id TEXT,
            fare_total_amount REAL,
            fare_amount_without_tax REAL,
            fare_tax REAL,
            fare_family TEXT,
            FOREIGN KEY (payload_id) REFERENCES search_response(payload_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE flight (
            payload_id TEXT,
            flight_idx INTEGER,
            origin_airport_code TEXT,
            destination_airport_code TEXT,
            departure_date TEXT,
            FOREIGN KEY (payload_id) REFERENCES search_response(payload_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE airport (
            payload_id TEXT,
            airport_code TEXT,
            city_name TEXT,
            country_name TEXT
        )
    """)
    
    # Insert test data
    # Search response for a SIN-BKK search
    cursor.execute("""
        INSERT INTO search_response (payload_id, session_id, trip_type, currency_code)
        VALUES ('payload-001', 'session-001', 'R', 'SGD')
    """)
    
    cursor.execute("""
        INSERT INTO search_response (payload_id, session_id, trip_type, currency_code)
        VALUES ('payload-002', 'session-002', 'R', 'SGD')
    """)
    
    # Recommendations with different prices
    cursor.execute("""
        INSERT INTO recommendation (payload_id, recommendation_id, fare_total_amount, fare_amount_without_tax, fare_tax, fare_family)
        VALUES ('payload-001', 'rec-001', 450.00, 400.00, 50.00, 'Economy')
    """)
    
    cursor.execute("""
        INSERT INTO recommendation (payload_id, recommendation_id, fare_total_amount, fare_amount_without_tax, fare_tax, fare_family)
        VALUES ('payload-002', 'rec-002', 520.00, 470.00, 50.00, 'Economy')
    """)
    
    # Flights
    cursor.execute("""
        INSERT INTO flight (payload_id, flight_idx, origin_airport_code, destination_airport_code, departure_date)
        VALUES ('payload-001', 0, 'SIN', 'BKK', '2019-09-15')
    """)
    
    cursor.execute("""
        INSERT INTO flight (payload_id, flight_idx, origin_airport_code, destination_airport_code, departure_date)
        VALUES ('payload-002', 0, 'SIN', 'BKK', '2019-09-20')
    """)
    
    # Airports
    cursor.execute("""
        INSERT INTO airport (payload_id, airport_code, city_name, country_name)
        VALUES ('payload-001', 'SIN', 'Singapore', 'Singapore')
    """)
    
    cursor.execute("""
        INSERT INTO airport (payload_id, airport_code, city_name, country_name)
        VALUES ('payload-001', 'BKK', 'Bangkok', 'Thailand')
    """)
    
    conn.commit()
    conn.close()
    
    return str(db_file)


@pytest.fixture
def sql_executor(test_db_path: str) -> SQLExecutor:
    """
    SQLExecutor instance configured with test database.
    
    Args:
        test_db_path: Path to the test database (from test_db_path fixture)
    
    Returns:
        SQLExecutor: Instance ready to execute queries against test DB
    """
    return SQLExecutor(db_path=test_db_path)


@pytest.fixture
def invalid_db_path() -> str:
    """
    Invalid database path for testing connection failures.
    
    Returns:
        str: Path to a non-existent database file
    """
    return "/non/existent/path/to/database.db"


# ==============================================================================
# DATABASE CONNECTION TESTS
# ==============================================================================

class TestDatabaseConnection:
    """
    Tests for database connection establishment.
    
    These tests verify that the SQLExecutor can successfully establish
    connections to valid databases and handle connection failures gracefully.
    """

    def test_executor_connects_to_valid_database(self, test_db_path):
        """
        Test that SQLExecutor can connect to a valid database.
        
        Scenario: A valid database exists and SQLExecutor should be able
        to establish a connection to it.
        
        Expected: The executor is created without errors and can execute queries.
        """
        # SETUP: Create executor with valid database path
        executor = SQLExecutor(db_path=test_db_path)
        
        # ACT: Execute a simple query to verify connection works
        compiled_sql = CompiledSQL(
            request_id="test-conn-001",
            sql="SELECT 1 AS test_value",
            bound_params={}
        )
        
        result = executor.execute(compiled_sql)
        
        # ASSERT: Query executes successfully
        assert isinstance(result, SuccessResponse)
        assert result.status == "SUCCESS"
        assert isinstance(result.data, ResultSet)

    def test_connection_failure_returns_error(self, invalid_db_path):
        """
        Test that connection failure returns a meaningful ErrorResponse.
        
        Scenario: The database path doesn't exist or is inaccessible.
        The executor should handle this gracefully and return a useful error.
        
        Expected: ErrorResponse with code "connection_error" and helpful message.
        """
        # SETUP: Create executor with invalid database path
        executor = SQLExecutor(db_path=invalid_db_path)
        
        # ACT: Try to execute a query
        compiled_sql = CompiledSQL(
            request_id="test-conn-002",
            sql="SELECT 1 AS test_value",
            bound_params={}
        )
        
        result = executor.execute(compiled_sql)
        
        # ASSERT: Returns ErrorResponse with connection error details
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.request_id == "test-conn-002"
        assert result.error.code == "connection_error"
        assert "connection" in result.error.message.lower() or "database" in result.error.message.lower()
        assert result.error.component == "sql_executor"

    def test_connection_with_readonly_database(self, test_db_path):
        """
        Test connection to a read-only database file.
        
        Scenario: The database file exists but might be read-only.
        For SELECT queries, this should still work fine.
        
        Expected: Successful execution of SELECT queries.
        """
        # SETUP: Create executor with existing database
        executor = SQLExecutor(db_path=test_db_path)
        
        # ACT: Execute a SELECT query (read-only operation)
        compiled_sql = CompiledSQL(
            request_id="test-conn-003",
            sql="SELECT session_id FROM search_response LIMIT 1",
            bound_params={}
        )
        
        result = executor.execute(compiled_sql)
        
        # ASSERT: Query executes successfully
        assert isinstance(result, SuccessResponse)
        assert result.status == "SUCCESS"


# ==============================================================================
# SQL EXECUTION TESTS
# ==============================================================================

class TestSQLExecution:
    """
    Tests for SQL query execution.
    
    These tests verify that the SQLExecutor correctly executes various types
    of SQL queries with different parameters and conditions.
    """

    def test_execute_simple_select_query(self, sql_executor):
        """
        Test execution of a simple SELECT query without parameters.
        
        Scenario: Execute "SELECT 1 AS value" to verify basic query execution.
        
        Expected: SuccessResponse with one row containing the value.
        """
        # SETUP: Create a simple SQL query
        compiled_sql = CompiledSQL(
            request_id="test-exec-001",
            sql="SELECT 1 AS value",
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Verify successful execution and result
        assert isinstance(result, SuccessResponse)
        assert result.request_id == "test-exec-001"
        assert result.status == "SUCCESS"
        assert len(result.data.result_set) == 1
        assert result.data.result_set[0].data["value"] == 1

    def test_execute_query_with_bound_parameters(self, sql_executor):
        """
        Test execution of query with bound parameters.
        
        Scenario: Execute a query using :param_name style parameters.
        The SQLite driver should safely substitute these parameters.
        
        Expected: Parameters are correctly bound and query executes successfully.
        """
        # SETUP: Create SQL with parameterized query
        compiled_sql = CompiledSQL(
            request_id="test-exec-002",
            sql="SELECT * FROM search_response WHERE session_id = :session_id",
            bound_params={"session_id": "session-001"}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Verify parameter binding worked correctly
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) == 1
        assert result.data.result_set[0].data["session_id"] == "session-001"

    def test_execute_query_with_multiple_parameters(self, sql_executor):
        """
        Test execution with multiple bound parameters.
        
        Scenario: A query needs multiple parameters like origin, destination, dates.
        All parameters should be safely bound.
        
        Expected: All parameters are correctly substituted in the query.
        """
        # SETUP: SQL with multiple parameters
        compiled_sql = CompiledSQL(
            request_id="test-exec-003",
            sql="""
                SELECT * FROM flight 
                WHERE origin_airport_code = :origin 
                AND destination_airport_code = :destination
            """,
            bound_params={
                "origin": "SIN",
                "destination": "BKK"
            }
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Query executed with all parameters bound
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) >= 1
        # Verify the results match the parameters
        for row in result.data.result_set:
            assert row.data["origin_airport_code"] == "SIN"
            assert row.data["destination_airport_code"] == "BKK"

    def test_execute_query_with_aggregation(self, sql_executor):
        """
        Test execution of query with aggregation functions.
        
        Scenario: Execute a query with MIN(), MAX(), or COUNT() functions.
        These are common in the cheapest flight queries.
        
        Expected: Aggregation functions execute correctly and return results.
        """
        # SETUP: Query with MIN aggregation
        compiled_sql = CompiledSQL(
            request_id="test-exec-004",
            sql="""
                SELECT MIN(fare_total_amount) AS min_price
                FROM recommendation
            """,
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Aggregation works correctly
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) == 1
        # Should return the minimum price from our test data
        assert result.data.result_set[0].data["min_price"] == 450.00

    def test_execute_query_with_joins(self, sql_executor):
        """
        Test execution of query with table JOINs.
        
        Scenario: Execute a query that joins multiple tables, which is
        common in the flight pricing queries.
        
        Expected: JOIN operations work correctly and return combined data.
        """
        # SETUP: Query with JOIN
        compiled_sql = CompiledSQL(
            request_id="test-exec-005",
            sql="""
                SELECT sr.session_id, r.fare_total_amount, sr.currency_code
                FROM search_response sr
                JOIN recommendation r ON r.payload_id = sr.payload_id
                WHERE sr.session_id = :session_id
            """,
            bound_params={"session_id": "session-001"}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: JOIN executed successfully
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) >= 1
        # Verify joined data is present
        row = result.data.result_set[0]
        assert "session_id" in row.data
        assert "fare_total_amount" in row.data
        assert "currency_code" in row.data

    def test_execute_query_with_limit(self, sql_executor):
        """
        Test execution of query with LIMIT clause.
        
        Scenario: Execute a query with LIMIT to restrict result count.
        
        Expected: Only the specified number of rows are returned.
        """
        # SETUP: Query with LIMIT
        compiled_sql = CompiledSQL(
            request_id="test-exec-006",
            sql="SELECT * FROM search_response LIMIT :limit",
            bound_params={"limit": 1}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: LIMIT is respected
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) == 1


# ==============================================================================
# RESULT SET TESTS
# ==============================================================================

class TestResultSet:
    """
    Tests for result set structure and data mapping.
    
    These tests verify that query results are correctly mapped to ResultSet
    and Row objects with proper field names and values.
    """

    def test_result_set_structure(self, sql_executor):
        """
        Test that result set has correct structure.
        
        Expected Structure:
        - SuccessResponse contains ResultSet
        - ResultSet contains request_id and list of Row objects
        - Each Row contains data dictionary with column name -> value mappings
        """
        # SETUP: Execute a query
        compiled_sql = CompiledSQL(
            request_id="test-result-001",
            sql="SELECT session_id, currency_code FROM search_response LIMIT 1",
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Verify complete structure
        assert isinstance(result, SuccessResponse)
        assert isinstance(result.data, ResultSet)
        assert result.data.request_id == "test-result-001"
        assert isinstance(result.data.result_set, list)
        assert len(result.data.result_set) >= 1
        assert isinstance(result.data.result_set[0], Row)
        assert isinstance(result.data.result_set[0].data, dict)

    def test_row_contains_all_columns(self, sql_executor):
        """
        Test that each Row contains all selected columns.
        
        Scenario: SELECT multiple columns, verify all appear in Row.data.
        
        Expected: Row.data dictionary has keys for all selected columns.
        """
        # SETUP: Query selecting multiple columns
        compiled_sql = CompiledSQL(
            request_id="test-result-002",
            sql="""
                SELECT session_id, trip_type, currency_code 
                FROM search_response 
                LIMIT 1
            """,
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: All columns are present in the row
        row = result.data.result_set[0]
        assert "session_id" in row.data
        assert "trip_type" in row.data
        assert "currency_code" in row.data

    def test_row_data_types_preserved(self, sql_executor):
        """
        Test that data types are preserved in Row objects.
        
        Scenario: Query returns different data types (TEXT, REAL, INTEGER).
        Verify they are correctly converted to Python types.
        
        Expected: 
        - TEXT -> str
        - REAL -> float
        - INTEGER -> int
        """
        # SETUP: Query with different data types
        compiled_sql = CompiledSQL(
            request_id="test-result-003",
            sql="""
                SELECT 
                    'test_string' AS text_value,
                    123.45 AS real_value,
                    42 AS integer_value
            """,
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Data types are correct
        row = result.data.result_set[0]
        assert isinstance(row.data["text_value"], str)
        assert isinstance(row.data["real_value"], float)
        assert isinstance(row.data["integer_value"], int)
        assert row.data["text_value"] == "test_string"
        assert row.data["real_value"] == 123.45
        assert row.data["integer_value"] == 42

    def test_empty_result_set(self, sql_executor):
        """
        Test handling of queries that return no rows.
        
        Scenario: Query has WHERE clause that matches nothing.
        
        Expected: SuccessResponse with empty result_set list (not an error).
        """
        # SETUP: Query that returns no results
        compiled_sql = CompiledSQL(
            request_id="test-result-004",
            sql="SELECT * FROM search_response WHERE session_id = :session_id",
            bound_params={"session_id": "non-existent-session"}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Empty result set is success, not error
        assert isinstance(result, SuccessResponse)
        assert result.status == "SUCCESS"
        assert len(result.data.result_set) == 0

    def test_multiple_rows_in_result_set(self, sql_executor):
        """
        Test result set with multiple rows.
        
        Scenario: Query returns multiple rows (multiple flights/recommendations).
        
        Expected: All rows are present in result_set as separate Row objects.
        """
        # SETUP: Query that returns multiple rows
        compiled_sql = CompiledSQL(
            request_id="test-result-005",
            sql="SELECT * FROM search_response",
            bound_params={}
        )
        
        # ACT: Execute the query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Multiple rows returned
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) >= 2  # We inserted 2 rows in fixture
        # Each should be a separate Row object
        for row in result.data.result_set:
            assert isinstance(row, Row)
            assert isinstance(row.data, dict)

    def test_request_id_preserved_in_result_set(self, sql_executor):
        """
        Test that request_id is preserved throughout execution.
        
        The request_id must appear in both the response and the ResultSet
        for request tracing.
        """
        # SETUP: Execute query with specific request_id
        test_request_ids = ["req-abc-001", "req-xyz-002", "req-test-003"]
        
        for req_id in test_request_ids:
            compiled_sql = CompiledSQL(
                request_id=req_id,
                sql="SELECT 1 AS value",
                bound_params={}
            )
            
            # ACT: Execute the query
            result = sql_executor.execute(compiled_sql)
            
            # ASSERT: request_id preserved at all levels
            assert result.request_id == req_id
            assert result.data.request_id == req_id


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

class TestErrorHandling:
    """
    Tests for query execution error handling.
    
    These tests verify that the SQLExecutor handles various error conditions
    gracefully and returns meaningful error messages.
    """

    def test_sql_syntax_error_returns_error(self, sql_executor):
        """
        Test that SQL syntax errors return ErrorResponse.
        
        Scenario: The compiled SQL contains a syntax error (e.g., typo in SQL).
        This shouldn't happen if the compiler works correctly, but the executor
        should handle it gracefully if it does.
        
        Expected: ErrorResponse with code "execution_error" or "sql_error".
        """
        # SETUP: SQL with syntax error
        compiled_sql = CompiledSQL(
            request_id="test-error-001",
            sql="SELCT * FROM search_response",  # Typo: SELCT instead of SELECT
            bound_params={}
        )
        
        # ACT: Try to execute invalid SQL
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Returns ErrorResponse with SQL error details
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.request_id == "test-error-001"
        assert result.error.code in ["execution_error", "sql_error"]
        assert result.error.component == "sql_executor"
        # Error message should mention syntax or SQL
        assert "syntax" in result.error.message.lower() or "sql" in result.error.message.lower()

    def test_invalid_table_name_returns_error(self, sql_executor):
        """
        Test that querying non-existent table returns ErrorResponse.
        
        Scenario: SQL references a table that doesn't exist in the database.
        
        Expected: ErrorResponse indicating table doesn't exist.
        """
        # SETUP: Query referencing non-existent table
        compiled_sql = CompiledSQL(
            request_id="test-error-002",
            sql="SELECT * FROM non_existent_table",
            bound_params={}
        )
        
        # ACT: Try to execute query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Returns ErrorResponse
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.error.code in ["execution_error", "sql_error"]
        # Error should mention table or existence
        assert "table" in result.error.message.lower() or "exist" in result.error.message.lower()

    def test_invalid_column_name_returns_error(self, sql_executor):
        """
        Test that selecting non-existent column returns ErrorResponse.
        
        Scenario: SQL references a column that doesn't exist in the table.
        
        Expected: ErrorResponse indicating column doesn't exist.
        """
        # SETUP: Query referencing non-existent column
        compiled_sql = CompiledSQL(
            request_id="test-error-003",
            sql="SELECT non_existent_column FROM search_response",
            bound_params={}
        )
        
        # ACT: Try to execute query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Returns ErrorResponse
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.error.code in ["execution_error", "sql_error"]

    def test_parameter_binding_error_returns_error(self, sql_executor):
        """
        Test that missing parameter binding returns ErrorResponse.
        
        Scenario: SQL has :param placeholder but bound_params doesn't include it.
        
        Expected: ErrorResponse indicating parameter binding issue.
        """
        # SETUP: SQL expects parameter that's not provided
        compiled_sql = CompiledSQL(
            request_id="test-error-004",
            sql="SELECT * FROM search_response WHERE session_id = :session_id",
            bound_params={}  # Missing session_id parameter
        )
        
        # ACT: Try to execute query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Returns ErrorResponse
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.error.code in ["execution_error", "parameter_error", "sql_error"]

    def test_error_response_structure(self, sql_executor):
        """
        Test that ErrorResponse has correct structure.
        
        All errors must include:
        - request_id: For request tracing
        - status: "ERROR"
        - error.code: Machine-readable error code
        - error.message: Human-readable error message
        - error.component: "sql_executor"
        """
        # SETUP: Create an error condition
        compiled_sql = CompiledSQL(
            request_id="test-error-005",
            sql="INVALID SQL QUERY",
            bound_params={}
        )
        
        # ACT: Execute invalid query
        result = sql_executor.execute(compiled_sql)
        
        # ASSERT: Error response structure is correct
        assert isinstance(result, ErrorResponse)
        assert result.request_id == "test-error-005"
        assert result.status == "ERROR"
        assert result.error.code is not None
        assert result.error.message is not None
        assert result.error.component == "sql_executor"
        # Details are optional but helpful for debugging
        assert hasattr(result.error, "details")


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

class TestIntegration:
    """
    Integration tests simulating real-world query scenarios.
    
    These tests use realistic queries that would come from the SQL Compiler
    to verify end-to-end execution.
    """

    def test_cheapest_flight_query(self, sql_executor):
        """
        Test execution of a typical "cheapest flight" query.
        
        This is the most common query type in the system.
        """
        compiled_sql = CompiledSQL(
            request_id="test-int-001",
            sql="""
                SELECT sr.session_id, sr.currency_code, MIN(r.fare_total_amount) AS cheapest_price
                FROM search_response sr
                JOIN recommendation r ON r.payload_id = sr.payload_id
                WHERE sr.trip_type = :trip_type
                GROUP BY sr.session_id, sr.currency_code
                ORDER BY cheapest_price ASC
                LIMIT :limit
            """,
            bound_params={"trip_type": "R", "limit": 5}
        )
        
        result = sql_executor.execute(compiled_sql)
        
        assert isinstance(result, SuccessResponse)
        assert len(result.data.result_set) >= 1
        # Verify result has expected columns
        row = result.data.result_set[0]
        assert "session_id" in row.data
        assert "currency_code" in row.data
        assert "cheapest_price" in row.data

    def test_destination_search_query(self, sql_executor):
        """
        Test execution of a destination search query.
        
        Finds airports matching certain criteria.
        """
        compiled_sql = CompiledSQL(
            request_id="test-int-002",
            sql="""
                SELECT DISTINCT airport_code, city_name, country_name
                FROM airport
                WHERE country_name = :country
                LIMIT :limit
            """,
            bound_params={"country": "Thailand", "limit": 10}
        )
        
        result = sql_executor.execute(compiled_sql)
        
        assert isinstance(result, SuccessResponse)
        # Verify results match the country filter
        for row in result.data.result_set:
            assert row.data["country_name"] == "Thailand"
