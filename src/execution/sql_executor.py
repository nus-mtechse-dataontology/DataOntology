"""Execute compiled SQL against the configured database."""

import logging
from typing import Union

from sqlalchemy.exc import SQLAlchemyError

from dao.fact_flight_info_dao import FactFlightInfoDAO
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, ResultSet, Row


class SQLExecutor:
    """
    Executes compiled SQL queries against a database.
    
    The executor takes CompiledSQL objects (containing SQL and bound parameters)
    and executes them against the configured database, returning either:
    - SuccessResponse[ResultSet]: Query results as a list of Row objects
    - ErrorResponse: Error details if execution fails
    
    Result Mapping:
    - Postgres results are mapped to Row objects with data dictionaries
    - Column names are preserved as dictionary keys
    - Data types are automatically converted by sqlmodel (VARCHAR→str, NUMERIC→float, INTEGER→int)
    """

    def __init__(self, fact_flight_info_dao: FactFlightInfoDAO) -> None:
        """
        Initialize SQLExecutor with Fact Flight Info DAO.
        
        Args:
            fact_flight_info_dao: The Fact Flight Info DAO
        """
        self._dao = fact_flight_info_dao
        self._log = logging.getLogger("data_ontology")

    def execute(
        self, compiled_sql: CompiledSQL
    ) -> Union[SuccessResponse[ResultSet], ErrorResponse]:
        """
        Execute compiled SQL query against the database.
        
        Process:
        1. Fetch all results using the DAO
        2. Return ResultSet wrapped in SuccessResponse
        3. Handle errors and return ErrorResponse if any step fails
        
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
            result = executor.execute(compiled_sql.sql)
            
            # result is SuccessResponse[ResultSet] with:
            # - data.result_set: [Row(data={"origin": "SIN", "destination": "BKK", ...}), ...]
        """
        try:
            result_rows = self._dao.execute_raw_query(compiled_sql.sql, compiled_sql.bound_params)
            result_set = ResultSet(
                type="flights",
                request_id=compiled_sql.request_id,
                result_set=result_rows
            )

            self._log.info("[%s] Query returned %d row(s)", compiled_sql.request_id, len(result_set.result_set))
            self._log.debug("[%s] Result set: %s", compiled_sql.request_id, [row for row in result_set.result_set])

            return SuccessResponse[ResultSet](
                request_id=compiled_sql.request_id,
                status="SUCCESS",
                data=result_set
            )

        except SQLAlchemyError as e:
            self._log.error("[%s] SQL execution error: %s", compiled_sql.request_id, str(e))
            return ErrorResponse(
                request_id=compiled_sql.request_id,
                error=ErrorDetails(
                    code=str(e.code),
                    message = f"SQL execution error: {str(e)}",
                    component="sql_executor",
                    details={
                        "sql": compiled_sql.sql,
                        "bound_params": compiled_sql.bound_params,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
            )
