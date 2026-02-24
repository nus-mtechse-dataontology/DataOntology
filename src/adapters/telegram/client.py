"""Minimal Telegram Bot API client."""

from __future__ import annotations

import json
from urllib import error, request


class TelegramClient:
    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: int, text: str) -> None:
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = request.Request(
            url=f"{self._base_url}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=10) as resp:
                status = getattr(resp, "status", 200)
                if status >= 400:
                    raise RuntimeError(f"Telegram sendMessage failed with status {status}")
        except error.URLError as exc:
            raise RuntimeError(f"Telegram sendMessage request failed: {exc}") from exc
