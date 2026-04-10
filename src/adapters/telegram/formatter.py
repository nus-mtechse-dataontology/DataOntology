"""Format orchestration responses into Telegram message text."""

from adapters.telegram.interfaces import ResponseFormatter
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse


def build_telegram_text_from_response(
    response: SuccessResponse[QuestionResponse] | ErrorResponse,
) -> str:
    if isinstance(response, SuccessResponse):
        return response.data.response

    if isinstance(response, ErrorResponse):
        return f"{response.error.message} (request_id: {response.request_id})"

    return "Unable to process response. Please try again."


class TelegramFormatter(ResponseFormatter):
    def format(self, response: SuccessResponse[QuestionResponse] | ErrorResponse) -> str:
        return build_telegram_text_from_response(response)
