from unittest.mock import Mock
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.telegram.telegram_routes import telegram_router
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse
from models.telegram_model import Update, Message, Chat


@pytest.fixture
def orchestrator():
    return Mock()


@pytest.fixture
def app(orchestrator):
    app = FastAPI()
    app.include_router(telegram_router)
    app.state.orchestrator = orchestrator
    app.state.configured_secret = "correct-secret"
    app.state.telegram_handler = Mock()
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def valid_update():
    return Update(
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
    ).model_dump(by_alias=True)


@pytest.fixture
def success_response():
    return SuccessResponse(
        request_id="req-1",
        data=QuestionResponse(
            request_id="req-1",
            response="The cheapest flight is $120.",
        ),
    )


@pytest.fixture
def error_response():
    return ErrorResponse(
        request_id="req-1",
        error=ErrorDetails(
            code="invalid_intent",
            message="Could not determine intent.",
            component="semantic_validator",
        ),
    )


@pytest.mark.skip("Update Test Later")
def test_webhook_happy_path_returns_200(client, orchestrator, valid_update, success_response):
    orchestrator.handle_question.return_value = success_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "test"}
    )
    
    print(response.content)
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    orchestrator.handle_question.assert_called_once()


@pytest.mark.skip("Update Test Later")
def test_webhook_missing_bot_token_returns_500(client, valid_update):
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "test"}
    )

    assert response.status_code == 500
    assert response.json()["error"] == "telegram_token_missing"


def test_webhook_invalid_secret_returns_401(client, valid_update):
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_webhook_secret"


@pytest.mark.skip("Update Test Later")
def test_webhook_valid_secret_passes(client, orchestrator, valid_update, success_response, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correct-secret")
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_message", Mock())
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_typing", Mock())
    orchestrator.handle_question.return_value = success_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )

    assert response.status_code == 200


@pytest.mark.skip("Update Test Later")
def test_webhook_invalid_update_returns_400(client, orchestrator, monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_message", Mock())
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_typing", Mock())

    invalid_update = {"update_id": 1, "message": {"chat": {"id": 12345}}}  # missing text

    with caplog.at_level("ERROR", logger="data_ontology"):
        response = client.post(
            "/telegram/webhook",
            json=invalid_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
        )

    assert response.status_code == 400
    orchestrator.handle_question.assert_not_called()
    assert any("returning 400" in r.message for r in caplog.records)


@pytest.mark.skip("Update Test Later")
def test_webhook_orchestrator_error_still_delivers_message_and_returns_200(
    client, orchestrator, valid_update, error_response, monkeypatch
):
    send_message = Mock()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_message", send_message)
    monkeypatch.setattr("adapters.telegram.client.TelegramClient.send_typing", Mock())
    orchestrator.handle_question.return_value = error_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
    )

    # Webhook handled successfully — error is communicated to user via Telegram message
    assert response.status_code == 200
    send_message.assert_called_once()
    sent_text = send_message.call_args[0][1]
    assert "Could not determine intent." in sent_text
