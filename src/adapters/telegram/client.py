"""Minimal Telegram Bot API client."""

from __future__ import annotations

import json
import time

import requests
from requests import RequestException
from requests.exceptions import HTTPError


class TelegramClient:
    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session = requests.Session()
        self._timeout_seconds = 15
        self._max_attempts = 2
        self._retry_delay_seconds = 0.2

    def send_message(self, chat_id: int, text: str) -> None:
        payload = {"chat_id": chat_id, "text": text}
        url = f"{self._base_url}/sendMessage"

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._session.post(url, json=payload, timeout=self._timeout_seconds)
                response.raise_for_status()
                return
            except HTTPError as exc:
                status = getattr(exc.response, "status_code", "unknown")
                raise RuntimeError(f"Telegram sendMessage failed with status {status}") from exc
            except RequestException as exc:
                if attempt < self._max_attempts:
                    time.sleep(self._retry_delay_seconds * attempt)
                    continue
                raise RuntimeError(f"Telegram sendMessage request failed: {exc}") from exc
