"""
Comprehensive tests for SQL Compiler.

This test suite validates that the SQLCompiler correctly converts QueryPlan objects
into compiled SQL with proper parameter binding. Tests are organized by acceptance criteria:
1. SQL is generated only from predefined templates
2. SQL contains only read-only operations (SELECT)
3. SQL enforces a maximum row limit (LIMIT clause)
4. Parameters are safely bound (no string concatenation/SQL injection)
5. Response structure is correct (SuccessResponse or ErrorResponse)
"""

import pytest
from typing import Any, Dict

from compiler.sql_compiler import SQLCompiler
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import QueryPlan, CompiledSQL


# ==============================================================================
# FIXTURES - Reusable test data and objects
# ==============================================================================

@pytest.fixture
def semantic_model() -> Dict[str, Any]:
    """
    Semantic model with predefined intents and SQL templates.
    
    This fixture provides the semantic layer that defines what intents the system
    supports and their corresponding SQL templates. Each intent has:
    - description: What the intent does
    - required_params: List of parameters that must be provided
    - sql_template: The SQL template with :param_name placeholders for parameterized queries
    
    Returns:
        Dict with version, intents containing 3 sample flight query intents
    """
    return {
        "version": "1.1",
        "intents": {
            "cheapest_return_flight": {
                "description": "Find the lowest-priced return flight",
                "required_params": ["origin", "destination", "start_date", "end_date"],
                "sql_template": "SELECT sr.session_id, sr.currency_code, MIN(r.fare_total_amount) AS cheapest_return_price FROM search_response sr JOIN recommendation r ON r.payload_id = sr.payload_id WHERE f_out.origin_airport_code = :origin AND f_out.destination_airport_code = :destination AND date(f_out.departure_date) BETWEEN date(:start_date) AND date(:end_date) LIMIT :limit"
            },
            "destinations_under_budget_return": {
                "description": "List destinations under budget",
                "required_params": ["origin", "max_price", "start_date", "end_date"],
                "sql_template": "SELECT DISTINCT f_out.destination_airport_code AS destination FROM search_response sr JOIN recommendation r ON r.payload_id = sr.payload_id WHERE f_out.origin_airport_code = :origin AND r.fare_total_amount <= :max_price AND date(f_out.departure_date) BETWEEN date(:start_date) AND date(:end_date) LIMIT :limit"
            },
            "route_departure_options": {
                "description": "Return departure options between two airports",
                "required_params": ["origin", "destination", "start_date", "end_date"],
                "sql_template": "SELECT f.origin_airport_code, f.destination_airport_code, fs.departure_datetime FROM flight f JOIN flight_segment fs ON fs.payload_id = f.payload_id WHERE f.origin_airport_code = :origin AND f.destination_airport_code = :destination AND datetime(fs.departure_datetime) BETWEEN datetime(:start_date) AND datetime(:end_date) LIMIT :limit"
            }
        }
    }


@pytest.fixture
def sql_compiler() -> SQLCompiler:
    """
    SQLCompiler instance for use in tests.
    
    This is the main component being tested. It takes a QueryPlan and semantic_model,
    and returns either a SuccessResponse with CompiledSQL or an ErrorResponse.
    
    Returns:
        SQLCompiler: A fresh instance for each test
    """
    return SQLCompiler()


# ==============================================================================
# SUCCESS TESTS: Valid compilation scenarios
# ==============================================================================

class TestSuccessfulCompilation:
    """
    Tests for successful SQL compilation.
    
    These tests verify that when a valid QueryPlan is provided with all required
    parameters, the SQLCompiler successfully generates a SuccessResponse containing
    a CompiledSQL object with valid SQL and bound parameters.
    """

    def test_compile_cheapest_return_flight_all_params(self, sql_compiler, semantic_model):
        """
        Test successful compilation with all required parameters.
        
        Scenario: A user asks "Find the cheapest return flight from SIN to BKK".
        The LLM extracts the intent as 'cheapest_return_flight' and fills in:
        - origin: SIN (Singapore)
        - destination: BKK (Bangkok)
        - start_date, end_date: Travel date range
        - limit: Maximum results to return
        
        Expected Result:
        - SuccessResponse with status "SUCCESS"
        - CompiledSQL containing valid SQL and bound_params
        - request_id preserved for tracing
        """
        # SETUP: Create a QueryPlan with all required parameters filled in
        query_plan = QueryPlan(
            request_id="test-001",  # Unique identifier for tracking this query
            intent="cheapest_return_flight",  # Identifies which SQL template to use
            parameters={  # Extracted parameters from the user's question
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],  # No missing parameters - all required ones are filled
            confidence=0.95  # Semantic validator's confidence in this plan
        )

        # ACT: Compile the query plan into SQL
        result = sql_compiler.compile(query_plan, semantic_model)

        # ASSERT: Verify the response structure is correct
        # Check that we got a SuccessResponse (not ErrorResponse)
        assert isinstance(result, SuccessResponse)
        # Verify the request_id is preserved for tracing
        assert result.request_id == "test-001"
        # Verify the status is SUCCESS
        assert result.status == "SUCCESS"
        # Verify the data payload is a CompiledSQL object
        assert isinstance(result.data, CompiledSQL)
        
        # ASSERT: Verify the CompiledSQL has required fields with valid content
        compiled_sql = result.data
        # request_id must be preserved throughout
        assert compiled_sql.request_id == "test-001"
        # SQL should be a non-empty string
        assert compiled_sql.sql is not None
        assert len(compiled_sql.sql) > 0

    def test_compile_destinations_under_budget(self, sql_compiler, semantic_model):
        """Test successful compilation for budget-based query."""
        query_plan = QueryPlan(
            request_id="test-002",
            intent="destinations_under_budget_return",
            parameters={
                "origin": "SIN",
                "max_price": 300,
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 20
            },
            missing_params=[],
            confidence=0.88
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        assert isinstance(result, SuccessResponse)
        assert result.status == "SUCCESS"
        assert result.data.sql is not None

    def test_compile_route_departure_options(self, sql_compiler, semantic_model):
        """Test successful compilation for departure options query."""
        query_plan = QueryPlan(
            request_id="test-003",
            intent="route_departure_options",
            parameters={
                "origin": "BKK",
                "destination": "SIN",
                "start_date": "2019-09-12",
                "end_date": "2019-09-12",
                "limit": 50
            },
            missing_params=[],
            confidence=0.92
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        assert isinstance(result, SuccessResponse)
        assert result.status == "SUCCESS"
        assert isinstance(result.data, CompiledSQL)


# ==============================================================================
# TEMPLATE-BASED GENERATION TESTS
# ==============================================================================

class TestTemplateBased:
    """Tests verifying SQL is generated from predefined templates."""

    def test_sql_uses_template(self, sql_compiler, semantic_model):
        """Test that generated SQL is based on template."""
        query_plan = QueryPlan(
            request_id="test-004",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        generated_sql = result.data.sql

        # Verify SQL contains expected template keywords
        # Every SQL query should start with SELECT
        assert "SELECT" in generated_sql.upper()
        # Every SQL query should specify source tables with FROM
        assert "FROM" in generated_sql.upper()
        # WHERE clause provides the filtering conditions
        assert "WHERE" in generated_sql.upper()
        # LIMIT clause restricts number of results
        assert "LIMIT" in generated_sql.upper()

    def test_sql_structure_matches_template(self, sql_compiler, semantic_model):
        """Test that SQL structure matches the predefined template."""
        query_plan = QueryPlan(
            request_id="test-005",
            intent="cheapest_return_flight",
            parameters={
                "origin": "NYC",
                "destination": "LAX",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 5
            },
            missing_params=[],
            confidence=0.90
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        generated_sql = result.data.sql

        # Verify key template elements are present from the semantic layer
        # These table names are defined in the semantic_layer.json template
        assert "search_response" in generated_sql  # Main source table
        assert "recommendation" in generated_sql  # Joined table with pricing info
        # Verify LIMIT is present (from template)
        assert "LIMIT" in generated_sql.upper()


# ==============================================================================
# READ-ONLY OPERATIONS TESTS
# ==============================================================================

class TestReadOnlyOperations:
    """
    Tests verifying SQL contains only read-only operations.
    
    Security Requirement: The SQLCompiler must NEVER generate SQL that modifies
    the database. It should only support SELECT operations. This prevents users
    from accidentally or maliciously modifying the data.
    
    Tested Operations:
    - ✅ SELECT (allowed)
    - ❌ INSERT (forbidden)
    - ❌ UPDATE (forbidden)
    - ❌ DELETE (forbidden)
    - ❌ DROP (forbidden)
    """

    def test_no_insert_operations(self, sql_compiler, semantic_model):
        """
        Test that generated SQL does not contain INSERT operations.
        
        Why this matters: If the compiler could generate INSERT statements,
        an malicious query plan could insert false data into the database.
        """
        query_plan = QueryPlan(
            request_id="test-006",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        # Convert SQL to uppercase to make the check case-insensitive
        sql_upper = result.data.sql.upper()

        # Assert that no INSERT keyword appears in the SQL
        assert "INSERT" not in sql_upper

    def test_no_update_operations(self, sql_compiler, semantic_model):
        """
        Test that generated SQL does not contain UPDATE operations.
        
        Why this matters: UPDATE statements would allow modifying existing data
        in the database, violating immutability.
        """
        query_plan = QueryPlan(
            request_id="test-007",
            intent="route_departure_options",
            parameters={
                "origin": "BKK",
                "destination": "SIN",
                "start_date": "2019-09-12",
                "end_date": "2019-09-12",
                "limit": 50
            },
            missing_params=[],
            confidence=0.92
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_upper = result.data.sql.upper()

        assert "UPDATE" not in sql_upper

    def test_no_delete_operations(self, sql_compiler, semantic_model):
        """
        Test that generated SQL does not contain DELETE operations.
        
        Why this matters: DELETE statements would remove data from the database,
        causing data loss.
        """
        query_plan = QueryPlan(
            request_id="test-008",
            intent="destinations_under_budget_return",
            parameters={
                "origin": "SIN",
                "max_price": 300,
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 20
            },
            missing_params=[],
            confidence=0.88
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_upper = result.data.sql.upper()

        assert "DELETE" not in sql_upper

    def test_no_drop_operations(self, sql_compiler, semantic_model):
        """
        Test that generated SQL does not contain DROP operations.
        
        Why this matters: DROP statements would delete entire tables or databases,
        causing catastrophic data loss.
        """
        query_plan = QueryPlan(
            request_id="test-009",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_upper = result.data.sql.upper()

        assert "DROP" not in sql_upper

    def test_select_operation_present(self, sql_compiler, semantic_model):
        """
        Test that generated SQL contains SELECT operation.
        
        This is the ONLY operation we want to support - reading data
        without modifying it.
        """
        query_plan = QueryPlan(
            request_id="test-010",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_upper = result.data.sql.upper()

        # Every query must have a SELECT clause
        assert "SELECT" in sql_upper


# ==============================================================================
# ROW LIMIT ENFORCEMENT TESTS
# ==============================================================================

class TestRowLimitEnforcement:
    """
    Tests verifying SQL enforces maximum row limit.
    
    Why this matters: Queries could return massive result sets that crash the
    system. The LIMIT clause prevents this by capping the number of rows returned.
    
    Each query must include a LIMIT clause with a parameter to control the
    maximum number of results.
    """

    def test_limit_clause_present(self, sql_compiler, semantic_model):
        """
        Test that generated SQL contains LIMIT clause.
        
        Every query must have a LIMIT clause to prevent returning too many rows
        which could:
        - Consume too much memory
        - Make the application unresponsive
        - Overwhelm the client
        """
        query_plan = QueryPlan(
            request_id="test-011",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_upper = result.data.sql.upper()

        # LIMIT clause must be present
        assert "LIMIT" in sql_upper

    def test_limit_param_bound_correctly(self, sql_compiler, semantic_model):
        """
        Test that :limit parameter is bound correctly.
        
        The LIMIT value must come from bound_params (parameterized query),
        not hardcoded in the SQL. This ensures:
        - The limit value can be changed dynamically
        - Security: no SQL injection through the limit parameter
        """
        query_plan = QueryPlan(
            request_id="test-012",
            intent="route_departure_options",
            parameters={
                "origin": "BKK",
                "destination": "SIN",
                "start_date": "2019-09-12",
                "end_date": "2019-09-12",
                "limit": 100  # Request 100 results
            },
            missing_params=[],
            confidence=0.92
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        
        # The 'limit' parameter must be in the bound_params dictionary
        assert "limit" in result.data.bound_params
        # The value must be correctly preserved
        assert result.data.bound_params["limit"] == 100

    def test_different_limit_values(self, sql_compiler, semantic_model):
        """
        Test LIMIT clause with different limit values.
        
        Different users might want different numbers of results.
        This test verifies the system handles various limit values correctly.
        """
        # Test with different limit values
        for limit_value in [5, 25, 50, 100]:
            query_plan = QueryPlan(
                request_id=f"test-limit-{limit_value}",
                intent="cheapest_return_flight",
                parameters={
                    "origin": "SIN",
                    "destination": "BKK",
                    "start_date": "2019-09-01",
                    "end_date": "2019-09-30",
                    "limit": limit_value  # Different limit each iteration
                },
                missing_params=[],
                confidence=0.95
            )

            result = sql_compiler.compile(query_plan, semantic_model)
            
            # Verify the limit is correctly bound in each case
            assert result.data.bound_params["limit"] == limit_value


# ==============================================================================
# PARAMETER BINDING SAFETY TESTS
# ==============================================================================

class TestParameterBinding:
    """
    Tests verifying safe parameter binding (no SQL injection).
    
    SQL Injection Security: Parameters MUST be bound using parameterized queries,
    not concatenated into the SQL string. This prevents malicious input from
    breaking out of the query and executing arbitrary SQL.
    
    WRONG (Vulnerable to SQL injection):
        sql = "SELECT * FROM flights WHERE origin = '" + origin + "'"
    
    RIGHT (Safe with parameterized queries):
        sql = "SELECT * FROM flights WHERE origin = :origin"
        bound_params = {"origin": origin}
    """

    def test_parameters_stored_in_bound_params(self, sql_compiler, semantic_model):
        """
        Test that parameters are stored in bound_params, not concatenated.
        
        All parameters must be in the bound_params dictionary where the database
        driver can safely handle them, not embedded in the SQL string.
        """
        query_plan = QueryPlan(
            request_id="test-013",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        compiled = result.data

        # ALL parameters must be in bound_params dictionary
        assert compiled.bound_params["origin"] == "SIN"
        assert compiled.bound_params["destination"] == "BKK"
        assert compiled.bound_params["start_date"] == "2019-09-01"
        assert compiled.bound_params["end_date"] == "2019-09-30"

    def test_no_string_concatenation_in_sql(self, sql_compiler, semantic_model):
        """
        Test that parameters are not string concatenated in SQL.
        
        This is the KEY security test. The actual parameter VALUES should NOT
        appear in the SQL string. They should only appear as placeholders like
        :origin, :destination, etc.
        
        Example:
        - GOOD: "WHERE origin = :origin" with bound_params={"origin": "SIN"}
        - BAD:  "WHERE origin = 'SIN'" (vulnerable to injection)
        """
        query_plan = QueryPlan(
            request_id="test-014",
            intent="destinations_under_budget_return",
            parameters={
                "origin": "SIN",
                "max_price": 300,
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 20
            },
            missing_params=[],
            confidence=0.88
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_text = result.data.sql

        # The actual parameter values must NOT appear in the SQL string
        # (they're in bound_params instead)
        assert "SIN" not in sql_text  # Parameter value not in SQL
        assert "300" not in sql_text  # Price value not in SQL
        assert "2019-09-01" not in sql_text  # Date value not in SQL

    def test_parameterized_query_format(self, sql_compiler, semantic_model):
        """
        Test that SQL uses parameterized query format (:param_name).
        
        Instead of concatenating values, the SQL should use placeholders
        like :origin, :destination which are filled by the database driver
        when executing with bound_params.
        """
        query_plan = QueryPlan(
            request_id="test-015",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        sql_text = result.data.sql

        # The SQL should contain parameter placeholders (: prefix in SQLite)
        # At least some of the main parameters should be mentioned as placeholders
        assert ":origin" in sql_text or ":destination" in sql_text

    def test_special_characters_in_parameters(self, sql_compiler, semantic_model):
        """
        Test safe handling of special characters in parameters.
        
        This tests that the system properly safeguards against SQL injection
        even with special characters that could break out of SQL strings.
        """
        query_plan = QueryPlan(
            request_id="test-016",
            intent="destinations_under_budget_return",
            parameters={
                "origin": "SIN",
                "max_price": 300.50,  # Decimal number
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 20
            },
            missing_params=[],
            confidence=0.88
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        compiled = result.data

        # The special character (decimal point) is preserved in bound_params
        # where it's safe, not embedded in SQL string
        assert compiled.bound_params["max_price"] == 300.50


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

class TestErrorHandling:
    """
    Tests for error scenarios.
    
    When the SQLCompiler receives invalid input, it must gracefully handle
    the error and return an ErrorResponse with helpful error details instead
    of crashing or returning invalid SQL.
    """

    def test_invalid_intent_returns_error(self, sql_compiler, semantic_model):
        """
        Test that invalid intent returns ErrorResponse.
        
        If the intent doesn't exist in the semantic layer, the compiler cannot
        find a template, so it must return an error.
        
        Scenario: User asks a question that the system doesn't understand.
        The LLM tries to match it to an intent that doesn't exist in the config.
        """
        query_plan = QueryPlan(
            request_id="test-017",
            intent="non_existent_intent",  # This intent isn't in semantic_model.intents
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        # Should return ErrorResponse (not SuccessResponse)
        assert isinstance(result, ErrorResponse)
        # Status should be ERROR
        assert result.status == "ERROR"
        # request_id must be preserved for tracing
        assert result.request_id == "test-017"
        # Error code should indicate the problem
        assert result.error.code == "invalid_intent"
        # Error message should be informative
        assert "intent" in result.error.message.lower()

    def test_missing_required_parameters_returns_error(self, sql_compiler, semantic_model):
        """
        Test that missing required parameters return ErrorResponse.
        
        Each intent has required_params that must be provided. If required
        parameters are missing, we can't fill the template properly.
        
        Scenario: User asks "Find the cheapest flight" but doesn't specify
        where to/from. The LLM identifies missing_params but the compiler
        should still reject incomplete requests.
        """
        query_plan = QueryPlan(
            request_id="test-018",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK"
                # Missing: start_date, end_date (required for this intent)
            },
            missing_params=["start_date", "end_date"],  # Documented as missing
            confidence=0.80  # Lower confidence due to missing params
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        # Should return ErrorResponse due to missing parameters
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"
        assert result.error.code == "missing_parameters"

    def test_empty_parameters_returns_error(self, sql_compiler, semantic_model):
        """
        Test that empty parameters return ErrorResponse.
        
        If no parameters are provided at all, we can't fill any template,
        so compilation should fail.
        """
        query_plan = QueryPlan(
            request_id="test-019",
            intent="cheapest_return_flight",
            parameters={},  # No parameters provided
            missing_params=["origin", "destination", "start_date", "end_date"],
            confidence=0.50  # Very low confidence
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        # Should return ErrorResponse
        assert isinstance(result, ErrorResponse)
        assert result.status == "ERROR"

    def test_error_response_structure(self, sql_compiler, semantic_model):
        """
        Test that ErrorResponse has correct structure.
        
        Whenever an error occurs, the response must have:
        - request_id: For request tracing
        - status: "ERROR"
        - error.code: Machine-readable error code
        - error.message: Human-readable error message
        - error.component: Which component had the error
        """
        query_plan = QueryPlan(
            request_id="test-020",
            intent="invalid_intent",  # Will cause an error
            parameters={},
            missing_params=[],
            confidence=0.50
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        # Verify ErrorResponse structure
        assert isinstance(result, ErrorResponse)
        assert result.request_id == "test-020"
        assert result.status == "ERROR"
        # Error details must be populated
        assert result.error.code is not None
        assert result.error.message is not None
        assert result.error.component is not None


# ==============================================================================
# RESPONSE STRUCTURE TESTS
# ==============================================================================

class TestResponseStructure:
    """
    Tests verifying correct response structure.
    
    The SQLCompiler must always return responses in the correct format,
    whether success or error. The response structure is important for:
    - Client code knowing how to parse the response
    - Request tracking and debugging
    - Consistent error handling across the API
    """

    def test_success_response_has_all_fields(self, sql_compiler, semantic_model):
        """
        Test that SuccessResponse contains all required fields.
        
        A successful response must include:
        - request_id: For tracking which request produced this result
        - status: Should be "SUCCESS"
        - data: The CompiledSQL payload
        """
        query_plan = QueryPlan(
            request_id="test-021",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)

        # Check all required fields exist
        assert hasattr(result, "request_id")
        assert hasattr(result, "status")
        assert hasattr(result, "data")
        # Verify correct values
        assert result.request_id == "test-021"
        assert result.status == "SUCCESS"

    def test_compiled_sql_has_all_fields(self, sql_compiler, semantic_model):
        """
        Test that CompiledSQL contains all required fields.
        
        The CompiledSQL object (inside result.data) must have:
        - request_id: For tracking (same as parent response)
        - sql: The actual SQL string to execute
        - bound_params: Dictionary of parameter values (can be empty but must exist)
        """
        query_plan = QueryPlan(
            request_id="test-022",
            intent="cheapest_return_flight",
            parameters={
                "origin": "SIN",
                "destination": "BKK",
                "start_date": "2019-09-01",
                "end_date": "2019-09-30",
                "limit": 10
            },
            missing_params=[],
            confidence=0.95
        )

        result = sql_compiler.compile(query_plan, semantic_model)
        compiled_sql = result.data

        # Check all required fields exist
        assert hasattr(compiled_sql, "request_id")
        assert hasattr(compiled_sql, "sql")
        assert hasattr(compiled_sql, "bound_params")
        # Verify field types and content
        assert compiled_sql.request_id == "test-022"
        assert isinstance(compiled_sql.sql, str)
        assert isinstance(compiled_sql.bound_params, dict)

    def test_request_id_preserved(self, sql_compiler, semantic_model):
        """
        Test that request_id is preserved through compilation.
        
        The request_id acts as a unique identifier for this compilation request.
        It must be preserved at every level:
        - In the response: result.request_id
        - In the data payload: result.data.request_id
        
        This allows the entire request to be traced through the system.
        """
        test_request_ids = ["req-abc-123", "req-xyz-789", "req-test-001"]

        # Test with multiple different request IDs to ensure preservation
        for req_id in test_request_ids:
            query_plan = QueryPlan(
                request_id=req_id,  # Different ID for each test
                intent="cheapest_return_flight",
                parameters={
                    "origin": "SIN",
                    "destination": "BKK",
                    "start_date": "2019-09-01",
                    "end_date": "2019-09-30",
                    "limit": 10
                },
                missing_params=[],
                confidence=0.95
            )

            result = sql_compiler.compile(query_plan, semantic_model)

            # request_id must be preserved at both levels
            assert result.request_id == req_id
            assert result.data.request_id == req_id
