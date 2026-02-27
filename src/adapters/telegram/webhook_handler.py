"""Telegram webhook handler orchestration adapter."""

from collections.abc import Callable
from typing import Any

from adapters.telegram.formatter import build_telegram_text_from_response
from adapters.telegram.mapper import build_nlq_request_from_update
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


def handle_telegram_update(
    update: dict[str, Any],
    orchestrator_handle_question: Callable[
        [NLQRequest], SuccessResponse[QuestionResponse] | ErrorResponse
    ],
    send_message: Callable[[int, str], None],
    request_id_provider: Callable[[], str],
) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
    mapped = build_nlq_request_from_update(update, request_id_provider=request_id_provider)
    if isinstance(mapped, ErrorResponse):
        return mapped

    chat_id, nlq_request = mapped
    orchestration_response = orchestrator_handle_question(nlq_request)
    telegram_text = build_telegram_text_from_response(orchestration_response)

    try:
        send_message(chat_id, telegram_text)
    except Exception as exc:
        return ErrorResponse(
            request_id=nlq_request.request_id,
            error=ErrorDetails(
                code="telegram_delivery_failed",
                message=f"Failed to deliver Telegram message: {exc}",
                component="telegram_webhook",
            ),
        )

    return SuccessResponse(
        request_id=nlq_request.request_id,
        data={
            "chat_id": chat_id,
            "delivered": True,
        },
    )
