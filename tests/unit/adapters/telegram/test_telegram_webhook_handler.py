from unittest.mock import Mock

from adapters.telegram.webhook_handler import handle_telegram_update
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


def test_handle_telegram_update_happy_path_calls_orchestrator_and_sender():
    update = {
        "update_id": 9101,
        "message": {
            "message_id": 21,
            "chat": {"id": 777, "type": "private"},
            "text": "Show my top holdings",
        },
    }
    orchestrator = Mock(
        return_value=SuccessResponse(
            request_id="req-tg-h1",
            data=QuestionResponse(
                request_id="req-tg-h1",
                response="I found 2 matching records.",
            ),
        )
    )
    send_message = Mock()

    result = handle_telegram_update(
        update=update,
        orchestrator_handle_question=orchestrator,
        send_message=send_message,
        request_id_provider=lambda: "req-tg-h1",
    )

    assert isinstance(result, SuccessResponse)
    assert result.request_id == "req-tg-h1"
    assert result.status == "SUCCESS"
    orchestrator.assert_called_once()
    nlq_request = orchestrator.call_args[0][0]
    assert isinstance(nlq_request, NLQRequest)
    assert nlq_request.question == "Show my top holdings"
    send_message.assert_called_once_with(777, "I found 2 matching records.")


def test_handle_telegram_update_orchestrator_error_still_sends_message():
    update = {
        "update_id": 9102,
        "message": {
            "message_id": 22,
            "chat": {"id": 888, "type": "private"},
            "text": "Show my top holdings",
        },
    }
    orchestrator = Mock(
        return_value=ErrorResponse(
            request_id="req-tg-h2",
            error=ErrorDetails(
                code="invalid_syntax",
                message="Malformed LLM output",
                component="syntactic_validator",
            ),
        )
    )
    send_message = Mock()

    result = handle_telegram_update(
        update=update,
        orchestrator_handle_question=orchestrator,
        send_message=send_message,
        request_id_provider=lambda: "req-tg-h2",
    )

    assert isinstance(result, SuccessResponse)
    assert result.request_id == "req-tg-h2"
    send_message.assert_called_once()
    sent_text = send_message.call_args[0][1]
    assert "Malformed LLM output" in sent_text


def test_handle_telegram_update_invalid_update_returns_error_and_skips_calls():
    update = {
        "update_id": 9103,
        "message": {
            "message_id": 23,
            "chat": {"id": 999, "type": "private"},
            # missing text
        },
    }
    orchestrator = Mock()
    send_message = Mock()

    result = handle_telegram_update(
        update=update,
        orchestrator_handle_question=orchestrator,
        send_message=send_message,
        request_id_provider=lambda: "req-tg-h3",
    )

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-tg-h3"
    assert result.error.component == "telegram_mapper"
    orchestrator.assert_not_called()
    send_message.assert_not_called()


def test_handle_telegram_update_send_failure_returns_delivery_error_response():
    update = {
        "update_id": 9104,
        "message": {
            "message_id": 24,
            "chat": {"id": 123, "type": "private"},
            "text": "Show my top holdings",
        },
    }
    orchestrator = Mock(
        return_value=SuccessResponse(
            request_id="req-tg-h4",
            data=QuestionResponse(
                request_id="req-tg-h4",
                response="I found 1 matching record.",
            ),
        )
    )
    send_message = Mock(side_effect=RuntimeError("Telegram unavailable"))

    result = handle_telegram_update(
        update=update,
        orchestrator_handle_question=orchestrator,
        send_message=send_message,
        request_id_provider=lambda: "req-tg-h4",
    )

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-tg-h4"
    assert result.error.component == "telegram_webhook"
    assert result.error.code == "telegram_delivery_failed"
