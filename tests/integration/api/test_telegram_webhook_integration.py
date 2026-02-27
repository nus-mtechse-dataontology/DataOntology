import asyncio

from adapters.telegram.client import TelegramClient
from endpoints.routes.telegram.telegram_routes import telegram_webhook


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


def test_telegram_webhook_returns_500_when_token_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    request = _FakeRequest({"message": {"chat": {"id": 1}, "text": "hello"}})

    response = asyncio.run(telegram_webhook(request=request))

    assert response.status_code == 500
    payload = response.body.decode("utf-8")
    assert "telegram_token_missing" in payload


def test_telegram_webhook_rejects_invalid_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    request = _FakeRequest({"message": {"chat": {"id": 1}, "text": "hello"}})

    response = asyncio.run(
        telegram_webhook(
            request=request,
            x_telegram_bot_api_secret_token="wrong-secret",
        )
    )

    assert response.status_code == 401
    payload = response.body.decode("utf-8")
    assert "invalid_webhook_secret" in payload


def test_telegram_webhook_returns_200_and_delivery_status(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(TelegramClient, "send_message", lambda self, chat_id, text: None)
    request = _FakeRequest({"message": {"chat": {"id": 123}, "text": "hello"}})

    response = asyncio.run(telegram_webhook(request=request))

    assert response.status_code == 200
    payload = response.body.decode("utf-8")
    assert '"status":"SUCCESS"' in payload
    assert '"chat_id":123' in payload
    assert '"delivered":true' in payload
