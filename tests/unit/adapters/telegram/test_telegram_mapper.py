from adapters.telegram import TelegramUpdateMapper
from models.common import ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest, QuestionResponse
from models.telegram_model import Update, Message, Chat

from datetime import datetime


def test_build_nlq_request_from_valid_update_returns_chat_id_and_nlq_request():
    update = Update(
        update_id=9001,
        message=Message(
            message_id=10,
            text="What are my top holdings?",
            chat=Chat(
                id=123456,
                type="private",
                first_name="test",
                last_name="user1",
                username="testuser1"
            ),
            date=int(datetime.now().timestamp())
        )
    )
    
    chat_id, request = TelegramUpdateMapper().map(update)

    assert chat_id == 123456
    assert isinstance(request, NLQRequest)
    assert request.request_id == "unknown"
    assert request.question == "What are my top holdings?"


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
