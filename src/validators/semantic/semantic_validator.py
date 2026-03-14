"""Semantic validator against semantic model intents and required params."""

import re
from typing import Any, Dict

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QueryPlan


class SemanticValidator:
    """
    Validates a QueryPlan against the semantic model.

    Checks:
        1. Intent exists in semantic_model["intents"]
        2. All required parameters for the intent are present
        3. No missing_params flagged by the LLM
        4. (Optional) Param format validation against param_schema

    Returns:
        SuccessResponse[QueryPlan] on success
        ErrorResponse on validation failure
    """

    COMPONENT_NAME = "semantic_validator"

    def validate(
        self,
        plan: QueryPlan,
        semantic_model: Dict[str, Any],
    ) -> SuccessResponse[QueryPlan] | ErrorResponse:
        """
        Validate QueryPlan against semantic model.

        Args:
            plan: Parsed query plan from syntactic validator
            semantic_model: Dictionary with structure:
                {
                    "intents": {
                        "intent_name": {
                            "required_params": ["param1", "param2"],
                            "sql_template": "SELECT ..."
                        }
                    },
                    "param_schema": {
                        "param_name": {"type": "string", "pattern": "..."}
                    }
                }

        Returns:
            SuccessResponse[QueryPlan] if valid
            ErrorResponse if validation fails
        """

        intents = semantic_model.get("intents", {})

        # -----------------------------------------------
        # 1. Validate intent exists
        # -----------------------------------------------
        if plan.intent not in intents:
            return self._error(
                request_id=plan.request_id,
                code="invalid_intent",
                message=f"Intent '{plan.intent}' not found in semantic model.",
                details={
                    "provided_intent": plan.intent,
                    "available_intents": list(intents.keys()),
                },
            )

        intent_def = intents[plan.intent]

        # -----------------------------------------------
        # 2. Validate required parameters are present
        # -----------------------------------------------
        required_params = intent_def.get("required_params", [])
        missing = [p for p in required_params if p not in plan.parameters]

        if missing:
            return self._error(
                request_id=plan.request_id,
                code="missing_required_params",
                message=f"Missing required parameters for intent '{plan.intent}': {', '.join(missing)}",
                details={
                    "intent": plan.intent,
                    "missing_params": missing,
                    "required_params": required_params,
                    "provided_params": list(plan.parameters.keys()),
                },
            )

        # -----------------------------------------------
        # 3. Check if LLM flagged missing params
        # -----------------------------------------------
        if plan.missing_params:
            return self._error(
                request_id=plan.request_id,
                code="llm_flagged_missing_params",
                message="LLM flagged missing required parameters in the query plan.",
                details={
                    "missing_params": plan.missing_params,
                    "follow_up_question": plan.follow_up_question,
                },
            )

        # -----------------------------------------------
        # 4. Validate param formats against param_schema
        # -----------------------------------------------
        param_schema = semantic_model.get("param_schema", {})
        for param_name, param_value in plan.parameters.items():
            if param_name in param_schema:
                schema = param_schema[param_name]
                pattern = schema.get("pattern")
                if pattern and isinstance(param_value, str):
                    if not re.match(pattern, param_value):
                        return self._error(
                            request_id=plan.request_id,
                            code="invalid_param_format",
                            message=f"Parameter '{param_name}' value '{param_value}' "
                                    f"does not match expected format.",
                            details={
                                "param_name": param_name,
                                "param_value": param_value,
                                "expected_pattern": pattern,
                                "expected_format": schema.get("format", "unknown"),
                            },
                        )

        # -----------------------------------------------
        # Success
        # -----------------------------------------------
        return SuccessResponse(
            request_id=plan.request_id,
            data=plan,
        )

    def _error(
        self,
        request_id: str,
        code: str,
        message: str,
        details: Dict[str, Any] | None = None,
    ) -> ErrorResponse:
        return ErrorResponse(
            request_id=request_id,
            error=ErrorDetails(
                code=code,
                message=message,
                component=self.COMPONENT_NAME,
                details=details,
            ),
        )