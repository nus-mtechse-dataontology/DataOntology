"""Telegram webhook handler orchestration adapter."""

import logging
from typing import Any

from adapters.telegram import TelegramUpdateMapper
from adapters.telegram.interfaces import MessageClient, ResponseFormatter
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.telegram_model import Update
from orchestrator import Orchestrator



class TelegramWebhookHandler:
    def __init__(
        self,
        mapper: TelegramUpdateMapper,
        orchestrator: Orchestrator,
        client: MessageClient,
        formatter: ResponseFormatter,
    ) -> None:
        self._mapper = mapper
        self._orchestrator = orchestrator
        self._client = client
        self._formatter = formatter
        
        self._log = logging.getLogger("data_ontology")

    def handle(self, update: Update) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        self._log.info("Webhook Handler: Attempting to handle new message... ")
        
        chat_id, nlq_request = self._mapper.map(update)
        self._safe_send_typing(chat_id, nlq_request.request_id)

        orchestration_response = self._orchestrator.handle_question(nlq_request)
        telegram_text = self._formatter.format(orchestration_response)

        return self._deliver_message(chat_id, nlq_request.request_id, telegram_text)

    def _safe_send_typing(self, chat_id: int, request_id: str) -> None:
        try:
            self._client.send_typing(chat_id)
        except Exception as exc:
            self._log.warning(
                "[%s] send_typing failed for chat_id=%s: %s",
                request_id,
                chat_id,
                exc,
            )
            raise exc

    def _deliver_message(
        self,
        chat_id: int,
        request_id: str,
        text: str,
    ) -> SuccessResponse[dict[str, Any]] | ErrorResponse:
        try:
            self._client.send_message(chat_id, text)
        except Exception as exc:
            self._log.error(
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
