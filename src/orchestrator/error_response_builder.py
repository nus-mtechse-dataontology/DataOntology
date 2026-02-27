"""Builds final user-facing error responses."""

from models.common import ErrorDetails, ErrorResponse


class ErrorResponseBuilder:
    def build(self, error_response: ErrorResponse) -> ErrorResponse:
        if isinstance(error_response, ErrorResponse):
            return error_response

        request_id = "unknown"
        if isinstance(error_response, dict):
            candidate = error_response.get("request_id")
            if isinstance(candidate, str) and candidate:
                request_id = candidate

        return ErrorResponse(
            request_id=request_id,
            error=ErrorDetails(
                code="invalid_error_response",
                message="error_response_builder requires an ErrorResponse payload",
                component="error_response_builder",
            ),
        )
