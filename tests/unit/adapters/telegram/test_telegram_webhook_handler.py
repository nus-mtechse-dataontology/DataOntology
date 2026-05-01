from unittest.mock import Mock
import pytest

from adapters.telegram.webhook_handler import TelegramWebhookHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, ResultSet
from models.telegram_model import Update, Message, Chat, MessageEntity, User

def _make_handler(orchestrator=None, send_message=None, send_typing=None, mapper=None):
    """Build a TelegramWebhookHandler with sensible defaults."""
    default_chat_id = 777
    default_request_id = "req-tg-1"

    if mapper is None:
        mapper = Mock()
        # The mapper.map in implementation now takes 'question' (str), not 'update'
        mapper.map.return_value = NLQRequest(request_id=default_request_id, question="test")

    if orchestrator is None:
        orchestrator = Mock()
        orchestrator.handle_question.return_value = SuccessResponse(
            request_id=default_request_id,
            data=ResultSet(request_id=default_request_id, type_="flights", result_set=[]),
        )

    client = Mock()
    client.send_message = send_message or Mock()
    client.send_typing = send_typing or Mock()

    return TelegramWebhookHandler(
        mapper=mapper,
        orchestrator=orchestrator,
        client=client,
    ), client


def test_handle_happy_path_calls_orchestrator_and_sender():
    handler, client = _make_handler()
    update = Update(
        update_id=1,
        message=Message(
            message_id=100,
            date=123456789,
            from_user=User(id=1, is_bot=False, first_name="test"),
            chat=Chat(id=777, type="private", first_name="test"),
            text="/flight test",
            entities=[MessageEntity(type="bot_command", offset=0, length=7)]
        )
    )

    result = handler.handle(update)

    assert isinstance(result, SuccessResponse)
    assert result.data["delivered"] is True
    client.send_message.assert_called_once()
    client.send_typing.assert_called_once()


def test_handle_orchestrator_error_still_sends_message():
    orchestrator = Mock()
    orchestrator.handle_question.return_value = ErrorResponse(
        request_id="req-tg-2",
        error=ErrorDetails(code="invalid_syntax", message="Malformed LLM output", component="syntactic_validator"),
    )

    handler, client = _make_handler(orchestrator=orchestrator)
    update = Update(
        update_id=1,
        message=Message(
            message_id=100,
            date=123456789,
            from_user=User(id=1, is_bot=False, first_name="test"),
            chat=Chat(id=777, type="private", first_name="test"),
            text="/flight test",
            entities=[MessageEntity(type="bot_command", offset=0, length=7)]
        )
    )
    result = handler.handle(update)

    assert isinstance(result, SuccessResponse)
    client.send_message.assert_called_once()
    sent_text = client.send_message.call_args[0][1]
    assert "Malformed LLM output" in sent_text


def test_handle_invalid_update_returns_error_and_skips_calls(caplog):
    mapper = Mock()
    # Note: implementation doesn't return ErrorResponse from mapper.map, it returns NLQRequest
    # This test might need implementation change in mapper.py if we want it to return ErrorResponse
    handler, client = _make_handler(mapper=mapper)
    
    result = handler.handle(Update(update_id=1)) # No message
    
    assert isinstance(result, ErrorResponse)
    assert result.error.component == "telegram_webhook"
    client.send_message.assert_not_called()
    client.send_typing.assert_not_called()


def test_handle_send_failure_returns_delivery_error(caplog):
    send_message = Mock(side_effect=RuntimeError("Telegram unavailable"))
    handler, client = _make_handler(send_message=send_message)
    update = Update(
        update_id=1,
        message=Message(
            message_id=100,
            date=123456789,
            from_user=User(id=1, is_bot=False, first_name="test"),
            chat=Chat(id=777, type="private", first_name="test"),
            text="/flight test",
            entities=[MessageEntity(type="bot_command", offset=0, length=7)]
        )
    )

    with caplog.at_level("ERROR", logger="data_ontology"):
        result = handler.handle(update)

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "telegram_delivery_failed"
    assert result.error.component == "telegram_webhook"
    assert any("send_message failed" in r.message and "Telegram unavailable" in r.message for r in caplog.records)


def test_handle_typing_failure_does_not_block_response(caplog):
    send_typing = Mock(side_effect=RuntimeError("typing failed"))
    handler, client = _make_handler(send_typing=send_typing)
    update = Update(
        update_id=1,
        message=Message(
            message_id=100,
            date=123456789,
            from_user=User(id=1, is_bot=False, first_name="test"),
            chat=Chat(id=777, type="private", first_name="test"),
            text="/flight test",
            entities=[MessageEntity(type="bot_command", offset=0, length=7)]
        )
    )

    with caplog.at_level("WARNING", logger="data_ontology"):
        result = handler.handle(update)

    assert isinstance(result, SuccessResponse)
    client.send_message.assert_called_once()
    assert any("send_typing failed" in r.message for r in caplog.records)
