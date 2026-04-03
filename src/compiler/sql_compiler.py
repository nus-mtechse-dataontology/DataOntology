"""Compile a validated QueryPlan into SQL and bound parameters."""

import logging
from typing import Any, Dict, Union

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import CompiledSQL, QueryPlan


class SQLCompiler:
    """
    Compiles validated QueryPlans into executable SQL with safe parameter binding.
    
    The compiler takes a QueryPlan (containing intent and parameters) and a semantic
    model (containing SQL templates for each intent), and returns either:
    - SuccessResponse[CompiledSQL]: SQL template filled with bound parameters
    - ErrorResponse: Error details if compilation fails
    
    Security: Parameters are never concatenated into SQL strings. Instead, they are
    passed in a bound_params dictionary using SQLite parameterized query format
    (e.g., :param_name) to prevent SQL injection.
    """

    def __init__(self) -> None:
        self._log = logging.getLogger("data_ontology")

    def compile(
        self, plan: QueryPlan, semantic_model: Dict[str, Any]
    ) -> Union[SuccessResponse[CompiledSQL], ErrorResponse]:
        """
        Compile a QueryPlan into SQL with bound parameters.
        
        Process:
        1. Validate the intent exists in the semantic model
        2. Check all required parameters are provided
        3. Get the SQL template for the intent
        4. Prepare bound parameters (no string concatenation)
        5. Return compiled SQL with parameterized query format
        
        Args:
            plan: QueryPlan containing intent and parameters to compile
            semantic_model: Dictionary with intents and SQL templates
                Expected structure: {
                    "intents": {
                        "intent_name": {
                            "required_params": ["param1", "param2"],
                            "sql_template": "SELECT ... WHERE x = :param1 AND y = :param2 LIMIT :limit"
                        }
                    }
                }
        
        Returns:
            SuccessResponse[CompiledSQL]: On success, contains SQL and bound_params
            ErrorResponse: On failure with error code and message
                Error Codes:
                - invalid_intent: Intent not found in semantic model
                - missing_parameters: Required parameters not provided
                - invalid_template: No SQL template for the intent
        
        Example:
            plan = QueryPlan(
                request_id="req-123",
                intent="cheapest_return_flight",
                parameters={"origin": "SIN", "destination": "BKK", "start_date": "2019-09-01", "end_date": "2019-09-30", "limit": 10},
                missing_params=[]
            )
            result = compiler.compile(plan, semantic_model)
            
            # result is SuccessResponse[CompiledSQL] with:
            # - sql: "SELECT ... WHERE origin = :origin AND destination = :destination LIMIT :limit"
            # - bound_params: {"origin": "SIN", "destination": "BKK", ..., "limit": 10}
        """
        
        # =======================================================================
        # STEP 1: Validate the intent exists in the semantic model
        # =======================================================================
        intents = semantic_model.get("intents", {})
        if plan.intent not in intents:
            return ErrorResponse(
                request_id=plan.request_id,
                error=ErrorDetails(
                    code="invalid_intent",
                    message=f"Intent '{plan.intent}' not found in semantic model. Available intents: {list(intents.keys())}",
                    component="sql_compiler",
                    details={"provided_intent": plan.intent, "available_intents": list(intents.keys())}
                )
            )
        
        intent_def = intents[plan.intent]
        
        # =======================================================================
        # STEP 2: Check all required parameters are provided
        # =======================================================================
        required_params = intent_def.get("required_params", [])
        
        # Find which required parameters are missing
        missing_params = [p for p in required_params if p not in plan.parameters]
        
        if missing_params:
            return ErrorResponse(
                request_id=plan.request_id,
                error=ErrorDetails(
                    code="missing_parameters",
                    message=f"Missing required parameters for intent '{plan.intent}': {', '.join(missing_params)}. Required: {', '.join(required_params)}",
                    component="sql_compiler",
                    details={
                        "intent": plan.intent,
                        "missing_params": missing_params,
                        "required_params": required_params,
                        "provided_params": list(plan.parameters.keys())
                    }
                )
            )
        
        # =======================================================================
        # STEP 3: Get the SQL template for this intent
        # =======================================================================
        sql_template = intent_def.get("sql_template")
        if not sql_template:
            return ErrorResponse(
                request_id=plan.request_id,
                error=ErrorDetails(
                    code="invalid_template",
                    message=f"No SQL template defined for intent '{plan.intent}'",
                    component="sql_compiler",
                    details={"intent": plan.intent}
                )
            )
        
        # =======================================================================
        # STEP 4: Prepare bound parameters
        # =======================================================================
        # Copy all parameters from the plan into bound_params
        # The SQL template uses :param_name placeholders which sqlite3 will replace
        # with values from this dictionary at execution time
        bound_params: Dict[str, Any] = dict(plan.parameters)
        
        # Ensure 'limit' parameter exists (defaults to 10 if not provided)
        if "limit" not in bound_params:
            bound_params["limit"] = 10

        # Inject None for any optional params not provided by the LLM
        for param in intent_def.get("optional_params", []):
            if param not in bound_params:
                bound_params[param] = None
        
        # =======================================================================
        # STEP 5: Return the compiled SQL
        # =======================================================================
        # The SQL is NOT modified - the template already contains:
        # - SELECT keyword (read-only operation only)
        # - Parameter placeholders like :origin, :destination (parameterized format)
        # - LIMIT clause (row limit enforcement)
        # - No string concatenation (safe from SQL injection)
        # All values are in bound_params, safely handled by the database driver
        
        compiled_sql = CompiledSQL(
            request_id=plan.request_id,
            sql=sql_template,
            bound_params=bound_params
        )

        self._log.info("[%s] SQL compiled for intent=%s", plan.request_id, plan.intent)
        self._log.debug("[%s] SQL: %s | params: %s", plan.request_id, sql_template, bound_params)

        return SuccessResponse[CompiledSQL](
            request_id=plan.request_id,
            status="SUCCESS",
            data=compiled_sql
        )
