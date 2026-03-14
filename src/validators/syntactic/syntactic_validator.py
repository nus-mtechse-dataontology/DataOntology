"""Syntactic validator for raw LLM output."""

import json

from pydantic import ValidationError

from llm_gateway.parser.raw_response import strip_markdown_fences
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import LLMRawResponse, QueryPlan


class SyntacticValidator:
    """
    Validates raw LLM output and converts it into QueryPlan.

    Process:
        1. Strip markdown fences from LLM output
        2. Parse JSON
        3. Inject request_id
        4. Validate schema using Pydantic (QueryPlan)
        5. Confidence range guard (0.0 to 1.0)

    Returns:
        SuccessResponse[QueryPlan] on success
        ErrorResponse on failure
    """

    def validate(
        self, raw_response: LLMRawResponse
    ) -> SuccessResponse[QueryPlan] | ErrorResponse:

        request_id = raw_response.request_id

        # Step 1: Strip markdown fences
        cleaned_text = strip_markdown_fences(raw_response.raw_response_text)

        # Step 2: Parse JSON
        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="malformed_json",
                    message="Malformed JSON returned by LLM.",
                    component="syntactic_validator",
                    details={"error": str(e)},
                ),
            )

        # Step 3: Inject request_id
        parsed["request_id"] = request_id

        # Step 4: Validate schema using Pydantic
        try:
            query_plan = QueryPlan(**parsed)
        except ValidationError as e:
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="schema_validation_error",
                    message="LLM output does not match QueryPlan schema.",
                    component="syntactic_validator",
                    details={"validation_errors": e.errors()},
                ),
            )

        # Step 5: Confidence range guard
        if not (0.0 <= query_plan.confidence <= 1.0):
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="invalid_confidence",
                    message="Confidence must be between 0 and 1.",
                    component="syntactic_validator",
                    details={"confidence": query_plan.confidence},
                ),
            )

        return SuccessResponse(
            request_id=request_id,
            data=query_plan,
        )