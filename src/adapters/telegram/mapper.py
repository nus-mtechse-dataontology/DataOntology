"""Map Telegram webhook updates into orchestration request contracts."""

from collections.abc import Callable
from typing import Any

from models.common import ErrorDetails, ErrorResponse
from models.pipeline import NLQRequest


def build_nlq_request_from_update(
    update: dict[str, Any], request_id_provider: Callable[[], str]
) -> tuple[int, NLQRequest] | ErrorResponse:
    request_id = request_id_provider()

    if not isinstance(update, dict):
        return ErrorResponse(
            request_id=request_id,
            error=ErrorDetails(
                code="invalid_telegram_update",
                message="Telegram update payload must be an object.",
                component="telegram_mapper",
            ),
        )

    message = update.get("message")
    if not isinstance(message, dict):
        return ErrorResponse(
            request_id=request_id,
            error=ErrorDetails(
                code="invalid_telegram_update",
                message="Telegram update does not contain a message object.",
                component="telegram_mapper",
            ),
        )

    chat = message.get("chat")
    text = message.get("text")
    chat_id = chat.get("id") if isinstance(chat, dict) else None

    if not isinstance(chat_id, int) or not isinstance(text, str) or not text.strip():
        return ErrorResponse(
            request_id=request_id,
            error=ErrorDetails(
                code="invalid_telegram_update",
                message="Telegram message must include chat.id and non-empty text.",
                component="telegram_mapper",
            ),
        )

    return chat_id, NLQRequest(
        request_id=request_id,
        question=text.strip(),
    )
