from adapters.telegram.formatter import build_telegram_text_from_response
from adapters.telegram.mapper import build_nlq_request_from_update
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse


def test_build_nlq_request_from_valid_update_returns_chat_id_and_nlq_request():
    update = {
        "update_id": 9001,
        "message": {
            "message_id": 10,
            "chat": {"id": 123456, "type": "private"},
            "text": "What are my top holdings?",
        },
    }

    chat_id, request = build_nlq_request_from_update(update, request_id_provider=lambda: "req-tg-1")

    assert chat_id == 123456
    assert isinstance(request, NLQRequest)
    assert request.request_id == "req-tg-1"
    assert request.question == "What are my top holdings?"


def test_build_nlq_request_from_invalid_update_returns_error_response():
    update = {
        "update_id": 9002,
        "message": {
            "message_id": 11,
            "chat": {"id": 123456, "type": "private"},
            # no text field
        },
    }

    result = build_nlq_request_from_update(update, request_id_provider=lambda: "req-tg-2")

    assert isinstance(result, ErrorResponse)
    assert result.request_id == "req-tg-2"
    assert result.error.component == "telegram_mapper"
    assert result.error.code == "invalid_telegram_update"
    assert result.error.message


def test_build_telegram_text_from_success_response_uses_question_response_text():
    success = SuccessResponse(
        request_id="req-tg-3",
        data=QuestionResponse(
            request_id="req-tg-3",
            response="I found 2 matching records.",
        ),
    )

    text = build_telegram_text_from_response(success)

    assert text == "I found 2 matching records."


def test_build_telegram_text_from_error_response_uses_human_readable_error_message():
    error = ErrorResponse(
        request_id="req-tg-4",
        error={
            "code": "invalid_syntax",
            "message": "Malformed LLM output",
            "component": "syntactic_validator",
        },
    )

    text = build_telegram_text_from_response(error)

    assert "Malformed LLM output" in text
    assert "req-tg-4" in text
