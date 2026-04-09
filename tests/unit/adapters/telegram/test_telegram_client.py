from unittest.mock import Mock

import requests

from adapters.telegram.client import TelegramClient


class _FakeResponse:
    def raise_for_status(self):
        return None


def test_send_message_retries_once_on_transient_connection_error(monkeypatch):
    client = TelegramClient(bot_token="token")
    post = Mock(side_effect=[requests.ConnectionError("assign requested address"), _FakeResponse()])
    client._session.post = post
    sleep = Mock()
    monkeypatch.setattr("adapters.telegram.client.time.sleep", sleep)

    client.send_message(chat_id=123, text="hello")

    assert post.call_count == 2
    sleep.assert_called_once()