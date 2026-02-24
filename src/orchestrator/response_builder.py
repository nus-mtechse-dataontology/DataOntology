"""Builds final user-facing responses from execution results."""

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse, ResultSet


class ResponseBuilder:
    def build(self, result_set: ResultSet) -> SuccessResponse[QuestionResponse] | ErrorResponse:
        if not isinstance(result_set, ResultSet):
            request_id = "unknown"
            if isinstance(result_set, dict):
                candidate = result_set.get("request_id")
                if isinstance(candidate, str) and candidate:
                    request_id = candidate
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="invalid_result_set",
                    message="response_builder requires a ResultSet payload",
                    component="response_builder",
                ),
            )

        row_count = len(result_set.result_set)
        if row_count == 0:
            response_text = "I could not find any matching records."
        else:
            record_lines = [
                f"{index}. {row.data}"
                for index, row in enumerate(result_set.result_set, start=1)
            ]
            header = "record" if row_count == 1 else "records"
            response_text = f"I found {row_count} matching {header}:\n" + "\n".join(record_lines)

        return SuccessResponse(
            request_id=result_set.request_id,
            data=QuestionResponse(
                request_id=result_set.request_id,
                response=response_text,
            ),
        )
