import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Header, Request, status, Depends
from fastapi.responses import JSONResponse

from models.common import ErrorResponse
from models.telegram_model import Update


_log = logging.getLogger("data_ontology")

telegram_router = APIRouter(prefix="/telegram", tags=["telegram"])


async def check_telegram_webhook_secret(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str, Header()]
) -> bool:
    return x_telegram_bot_api_secret_token == request.app.state.configured_secret


@telegram_router.post("/webhook")
async def telegram_webhook(
    request: Request,
    payload: Update,
    verified: Annotated[bool, Depends(check_telegram_webhook_secret)]
):
    _log.info(
        "Telegram Webhook: Received request from: (%s)",
        payload.message.from_user if payload.message else payload.edited_message.from_user
    )

    if not verified:
        _log.error("Telegram Webhook: Invalid Secret Token...")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_webhook_secret",
                "message": "Invalid Telegram webhook secret token.",
            },
        )

    handler = request.app.state.telegram_handler
    
    task = await asyncio.gather(
        asyncio.to_thread(
            handle_request,
            handler,
            payload
        )
    )
    result = task[0]

    if isinstance(result, ErrorResponse):
        _log.error(
            "[%s] Telegram webhook returning 400 [%s]: %s",
            result.request_id, result.error.code, result.error.message
        )

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(),
    )


@telegram_router.post("/webhook/debug")
async def telegram_webhook(
    request: Request,
):
    response = await request.json()
    _log.info("Webhook Debug: Received request from: (%s)", response)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "debug": response,
        }
    )


def handle_request(handler, payload):
    return handler.handle(payload)
