import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from adapters.telegram.client import TelegramClient
from adapters.telegram.webhook_handler import handle_telegram_update
from models.common import ErrorResponse

_log = logging.getLogger("data_ontology")

telegram_router = APIRouter(prefix="/telegram", tags=["telegram"])


@telegram_router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    configured_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if configured_secret and x_telegram_bot_api_secret_token != configured_secret:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_webhook_secret",
                "message": "Invalid Telegram webhook secret token.",
            },
        )

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "telegram_token_missing",
                "message": "TELEGRAM_BOT_TOKEN is not configured.",
            },
        )

    payload = await request.json()
    telegram_client = TelegramClient(bot_token=bot_token)
    result = handle_telegram_update(
        update=payload,
        orchestrator_handle_question=request.app.state.orchestrator.handle_question,
        send_message=telegram_client.send_message,
        send_typing_action=telegram_client.send_typing_action,
        request_id_provider=lambda: str(uuid4()),
    )

    if isinstance(result, ErrorResponse):
        _log.error("[%s] Telegram webhook returning 400 [%s]: %s", result.request_id, result.error.code, result.error.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(),
    )
