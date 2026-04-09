"""Telegram webhook handler orchestration adapter."""

import logging
from collections.abc import Callable
from typing import Any

from adapters.telegram.interfaces import MessageClient, ResponseFormatter, UpdateMapper
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse

_log = logging.getLogger("data_ontology")


class TelegramWebhookHandler:
    def __init__(
        self,
        mapper: UpdateMapper,
        orchestrator_handle_question: Callable[
            [NLQRequest], SuccessResponse[QuestionResponse] | ErrorResponse
        ],
        client: MessageClient,
        formatter: ResponseFormatter,
    ) -> None:
        self._mapper = mapper
        self._orchestrator_handle_question = orchestrator_handle_question
        self._client = client
        self._formatter = formatter

    def handle(self, update: dict[str, Any]) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        mapped = self._mapper.map(update)

        if isinstance(mapped, ErrorResponse):
            _log.error(
                "[%s] Mapper failed [%s]: %s",
                mapped.request_id,
                mapped.error.code,
                mapped.error.message,
            )
            return mapped

        chat_id, nlq_request = mapped

        self._safe_send_typing(chat_id, nlq_request.request_id)

        orchestration_response = self._orchestrator_handle_question(nlq_request)
        telegram_text = self._formatter.format(orchestration_response)

        return self._deliver_message(chat_id, nlq_request.request_id, telegram_text)

    def _safe_send_typing(self, chat_id: int, request_id: str) -> None:
        try:
            self._client.send_typing(chat_id)
        except Exception as exc:
            _log.warning(
                "[%s] send_typing failed for chat_id=%s: %s",
                request_id,
                chat_id,
                exc,
            )

    def _deliver_message(
        self,
        chat_id: int,
        request_id: str,
        text: str,
    ) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        try:
            self._client.send_message(chat_id, text)
        except Exception as exc:
            _log.error(
                "[%s] send_message failed for chat_id=%s: %s",
                request_id,
                chat_id,
                exc,
            )
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetails(
                    code="telegram_delivery_failed",
                    message=f"Failed to deliver Telegram message: {exc}",
                    component="telegram_webhook",
                ),
            )

        return SuccessResponse(
            request_id=request_id,
            data={"chat_id": chat_id, "delivered": True},
        )
