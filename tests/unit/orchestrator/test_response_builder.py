from models.common import ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse, ResultSet, Row
from orchestrator.response_builder import ResponseBuilder


def test_build_returns_success_response_wrapping_question_response():
    builder = ResponseBuilder()
    result_set = ResultSet(
        request_id="req-123",
        result_set=[Row(data={"value": 1000})],
    )

    result = builder.build(result_set)

    assert isinstance(result, SuccessResponse)
    assert result.request_id == "req-123"
    assert result.status == "SUCCESS"
    assert isinstance(result.data, QuestionResponse)
    assert result.data.request_id == "req-123"
    assert result.data.response


def test_build_returns_error_response_when_input_is_not_result_set():
    builder = ResponseBuilder()

    result = builder.build({"request_id": "req-123", "result_set": []})  # type: ignore[arg-type]

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-123"
    assert result.status == "ERROR"
    assert result.error.component == "response_builder"
    assert result.error.code
    assert result.error.message


def test_build_zero_rows_message_reports_no_records():
    builder = ResponseBuilder()
    result_set = ResultSet(request_id="req-123", result_set=[])

    result = builder.build(result_set)

    assert isinstance(result, SuccessResponse)
    assert result.data.response == "I could not find any matching records."


def test_build_single_row_count_matches_displayed_records():
    builder = ResponseBuilder()
    result_set = ResultSet(
        request_id="req-123",
        result_set=[Row(data={"value": 1000})],
    )

    result = builder.build(result_set)

    assert isinstance(result, SuccessResponse)
    lines = result.data.response.splitlines()
    assert lines[0].startswith("I found 1 matching record")
    displayed_rows = [line for line in lines[1:] if line.startswith("1. ")]
    assert len(displayed_rows) == 1


def test_build_multi_row_count_matches_displayed_records():
    builder = ResponseBuilder()
    result_set = ResultSet(
        request_id="req-123",
        result_set=[
            Row(data={"id": 1, "value": 100}),
            Row(data={"id": 2, "value": 200}),
            Row(data={"id": 3, "value": 300}),
        ],
    )

    result = builder.build(result_set)

    assert isinstance(result, SuccessResponse)
    lines = result.data.response.splitlines()
    assert lines[0].startswith("I found 3 matching records")
    displayed_rows = [line for line in lines[1:] if line[:2] in {"1.", "2.", "3."}]
    assert len(displayed_rows) == 3
