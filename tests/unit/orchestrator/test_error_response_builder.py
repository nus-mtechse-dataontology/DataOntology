from models.common import ErrorDetails, ErrorResponse
from orchestrator.error_response_builder import ErrorResponseBuilder


def test_build_returns_error_response_contract():
    builder = ErrorResponseBuilder()
    error = ErrorResponse(
        request_id="req-123",
        error=ErrorDetails(
            code="stage_failed",
            message="LLM unavailable",
            component="llm_gateway",
        ),
    )

    result = builder.build(error)

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-123"
    assert result.status == "ERROR"
    assert result.error.code == "stage_failed"
    assert result.error.message == "LLM unavailable"
    assert result.error.component == "llm_gateway"


def test_build_returns_invalid_request_error_for_non_error_response_input():
    builder = ErrorResponseBuilder()

    result = builder.build({"request_id": "req-123"})  # type: ignore[arg-type]

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-123"
    assert result.status == "ERROR"
    assert result.error.component == "error_response_builder"
    assert result.error.code == "invalid_error_response"
    assert result.error.message
