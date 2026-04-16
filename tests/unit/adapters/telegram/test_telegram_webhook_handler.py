from unittest.mock import Mock

import pytest

from adapters.telegram.webhook_handler import TelegramWebhookHandler
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


def _make_handler(orchestrator=None, send_message=None, send_typing=None, mapper=None, formatter=None):
    """Build a TelegramWebhookHandler with sensible defaults."""
    default_chat_id = 777
    default_request_id = "req-tg-1"

    if mapper is None:
        mapper = Mock()
        mapper.map.return_value = (default_chat_id, NLQRequest(request_id=default_request_id, question="test"))

    if orchestrator is None:
        orchestrator = Mock(
            return_value=SuccessResponse(
                request_id=default_request_id,
                data=QuestionResponse(request_id=default_request_id, response="Here are your results."),
            )
        )

    client = Mock()
    client.send_message = send_message or Mock()
    client.send_typing = send_typing or Mock()

    if formatter is None:
        formatter = Mock()
        formatter.format.return_value = "Here are your results."

    return TelegramWebhookHandler(
        mapper=mapper,
        orchestrator=orchestrator,
        client=client,
        formatter=formatter,
    ), client


def test_handle_happy_path_calls_orchestrator_and_sender():
    handler, client = _make_handler()
    update = {"update_id": 1}

    result = handler.handle(update)

    assert isinstance(result, SuccessResponse)
    assert result.data["delivered"] is True
    client.send_message.assert_called_once()
    client.send_typing.assert_called_once()


def test_handle_orchestrator_error_still_sends_message():
    orchestrator = Mock(
        return_value=ErrorResponse(
            request_id="req-tg-2",
            error=ErrorDetails(code="invalid_syntax", message="Malformed LLM output", component="syntactic_validator"),
        )
    )
    formatter = Mock()
    formatter.format.return_value = "Malformed LLM output (request_id: req-tg-2)"

    handler, client = _make_handler(orchestrator=orchestrator, formatter=formatter)
    result = handler.handle({})

    assert isinstance(result, SuccessResponse)
    client.send_message.assert_called_once()
    sent_text = client.send_message.call_args[0][1]
    assert "Malformed LLM output" in sent_text


@pytest.mark.skip("Update Test Later")
def test_handle_invalid_update_returns_error_and_skips_calls(caplog):
    mapper = Mock()
    mapper.map.return_value = ErrorResponse(
        request_id="req-tg-3",
        error=ErrorDetails(code="invalid_telegram_update", message="Missing text", component="telegram_mapper"),
    )
    handler, client = _make_handler(mapper=mapper)

    with caplog.at_level("ERROR", logger="data_ontology"):
        result = handler.handle({})

    assert isinstance(result, ErrorResponse)
    assert result.error.component == "telegram_mapper"
    client.send_message.assert_not_called()
    client.send_typing.assert_not_called()
    assert any("Mapper failed" in r.message for r in caplog.records)


# @pytest.mark.skip("Update Test Later")
def test_handle_send_failure_returns_delivery_error(caplog):
    send_message = Mock(side_effect=RuntimeError("Telegram unavailable"))
    handler, client = _make_handler(send_message=send_message)

    with caplog.at_level("ERROR", logger="data_ontology"):
        result = handler.handle({})

    assert isinstance(result, ErrorResponse)
    assert result.error.code == "telegram_delivery_failed"
    assert result.error.component == "telegram_webhook"
    assert any("send_message failed" in r.message and "Telegram unavailable" in r.message for r in caplog.records)


@pytest.mark.skip("Update Test Later")
def test_handle_typing_failure_does_not_block_response(caplog):
    send_typing = Mock(side_effect=RuntimeError("typing failed"))
    handler, client = _make_handler(send_typing=send_typing)

    with caplog.at_level("WARNING", logger="data_ontology"):
        result = handler.handle({})

    assert isinstance(result, SuccessResponse)
    client.send_message.assert_called_once()
    assert any("send_typing failed" in r.message for r in caplog.records)
