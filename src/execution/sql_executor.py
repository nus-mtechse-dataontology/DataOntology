"""Execute compiled SQL against the configured database."""

import sqlite3
from typing import Any, Dict, List, Union

from execution.db import get_connection
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, ResultSet, Row


class SQLExecutor:
    """
    Executes compiled SQL queries against a SQLite database.
    
    The executor takes CompiledSQL objects (containing SQL and bound parameters)
    and executes them against the configured database, returning either:
    - SuccessResponse[ResultSet]: Query results as a list of Row objects
    - ErrorResponse: Error details if execution fails
    
    Connection Management:
    - Uses the get_connection utility to establish database connections
    - Connections are opened for each query execution (no connection pooling)
    - Connections are properly closed in finally blocks to prevent leaks
    
    Result Mapping:
    - SQLite results are mapped to Row objects with data dictionaries
    - Column names are preserved as dictionary keys
    - Data types are automatically converted by sqlite3 (TEXT→str, REAL→float, INTEGER→int)
    """

    def __init__(self, db_path: str) -> None:
        """
        Initialize SQLExecutor with database path.
        
        Args:
            db_path: Path to the SQLite database file
        
        Note: The database connection is NOT established here. Connections
        are created on-demand during execute() calls.
        """
        self._db_path = db_path

    def execute(
        self, compiled_sql: CompiledSQL
    ) -> Union[SuccessResponse[ResultSet], ErrorResponse]:
        """
        Execute compiled SQL query against the database.
        
        Process:
        1. Establish database connection
        2. Execute SQL with bound parameters
        3. Fetch all results
        4. Map results to Row objects
        5. Return ResultSet wrapped in SuccessResponse
        6. Handle errors and return ErrorResponse if any step fails
        
        Args:
            compiled_sql: CompiledSQL object containing:
                - request_id: Unique identifier for tracing
                - sql: SQL query string with :param_name placeholders
                - bound_params: Dictionary of parameter values
        
        Returns:
            SuccessResponse[ResultSet]: On successful execution
                - Contains ResultSet with list of Row objects
                - Each Row has a data dict with column_name -> value
            ErrorResponse: On failure
                - connection_error: Database connection failed
                - execution_error: SQL execution failed (syntax, table/column errors, etc.)
                - parameter_error: Parameter binding failed
        
        Example:
            compiled_sql = CompiledSQL(
                request_id="req-123",
                sql="SELECT * FROM flights WHERE origin = :origin",
                bound_params={"origin": "SIN"}
            )
            result = executor.execute(compiled_sql)
            
            # result is SuccessResponse[ResultSet] with:
            # - data.result_set: [Row(data={"origin": "SIN", "destination": "BKK", ...}), ...]
        """
        
        conn = None
        cursor = None
        
        try:
            # ===================================================================
            # STEP 1: Establish database connection
            # ===================================================================
            try:
                conn = get_connection(self._db_path)
                cursor = conn.cursor()
            except sqlite3.Error as e:
                # Connection failed - database doesn't exist, permissions issue, etc.
                return ErrorResponse(
                    request_id=compiled_sql.request_id,
                    error=ErrorDetails(
                        code="connection_error",
                        message=f"Failed to connect to database: {str(e)}",
                        component="sql_executor",
                        details={
                            "db_path": self._db_path,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                )
            except Exception as e:
                # Unexpected connection error
                return ErrorResponse(
                    request_id=compiled_sql.request_id,
                    error=ErrorDetails(
                        code="connection_error",
                        message=f"Unexpected error connecting to database: {str(e)}",
                        component="sql_executor",
                        details={
                            "db_path": self._db_path,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                )
            
            # ===================================================================
            # STEP 2: Execute SQL with bound parameters
            # ===================================================================
            try:
                # Execute the SQL with parameterized binding
                # SQLite will safely substitute :param_name with values from bound_params
                cursor.execute(compiled_sql.sql, compiled_sql.bound_params)
            except sqlite3.OperationalError as e:
                # SQL execution error: syntax error, table doesn't exist, column doesn't exist, etc.
                error_msg = str(e).lower()
                
                # Determine more specific error code based on message
                if "no such table" in error_msg:
                    code = "execution_error"
                    message = f"Table does not exist: {str(e)}"
                elif "no such column" in error_msg:
                    code = "execution_error"
                    message = f"Column does not exist: {str(e)}"
                elif "syntax error" in error_msg:
                    code = "sql_error"
                    message = f"SQL syntax error: {str(e)}"
                else:
                    code = "execution_error"
                    message = f"SQL execution error: {str(e)}"
                
                return ErrorResponse(
                    request_id=compiled_sql.request_id,
                    error=ErrorDetails(
                        code=code,
                        message=message,
                        component="sql_executor",
                        details={
                            "sql": compiled_sql.sql,
                            "bound_params": compiled_sql.bound_params,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                )
            except sqlite3.ProgrammingError as e:
                # Parameter binding error: missing parameter, wrong parameter type, etc.
                return ErrorResponse(
                    request_id=compiled_sql.request_id,
                    error=ErrorDetails(
                        code="parameter_error",
                        message=f"Parameter binding error: {str(e)}",
                        component="sql_executor",
                        details={
                            "sql": compiled_sql.sql,
                            "bound_params": compiled_sql.bound_params,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                )
            except sqlite3.Error as e:
                # Other SQLite errors
                return ErrorResponse(
                    request_id=compiled_sql.request_id,
                    error=ErrorDetails(
                        code="execution_error",
                        message=f"Database error during execution: {str(e)}",
                        component="sql_executor",
                        details={
                            "sql": compiled_sql.sql,
                            "bound_params": compiled_sql.bound_params,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                )
            
            # ===================================================================
            # STEP 3: Fetch all results
            # ===================================================================
            rows = cursor.fetchall()
            
            # ===================================================================
            # STEP 4: Map results to Row objects
            # ===================================================================
            # Convert sqlite3.Row objects to our Row model
            # sqlite3.Row allows both index and key access, we use keys to build dict
            result_rows: List[Row] = []
            
            for sqlite_row in rows:
                # Convert sqlite3.Row to dictionary
                # sqlite_row.keys() gives column names
                row_dict: Dict[str, Any] = {}
                for key in sqlite_row.keys():
                    row_dict[key] = sqlite_row[key]
                
                # Create Row object with data dictionary
                result_rows.append(Row(data=row_dict))
            
            # ===================================================================
            # STEP 5: Return ResultSet wrapped in SuccessResponse
            # ===================================================================
            result_set = ResultSet(
                request_id=compiled_sql.request_id,
                result_set=result_rows
            )
            
            return SuccessResponse[ResultSet](
                request_id=compiled_sql.request_id,
                status="SUCCESS",
                data=result_set
            )
        
        except Exception as e:
            # Catch-all for unexpected errors during execution
            return ErrorResponse(
                request_id=compiled_sql.request_id,
                error=ErrorDetails(
                    code="execution_error",
                    message=f"Unexpected error during query execution: {str(e)}",
                    component="sql_executor",
                    details={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            )
        
        finally:
            # ===================================================================
            # CLEANUP: Always close the database connection
            # ===================================================================
            # Proper cleanup prevents connection leaks and locks
            if cursor:
                cursor.close()
            if conn:
                conn.close()
