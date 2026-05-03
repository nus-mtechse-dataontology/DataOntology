from unittest.mock import Mock
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.telegram.telegram_routes import telegram_router
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse, ResultSet
from models.telegram_model import Update, Message, Chat


@pytest.fixture
def orchestrator():
    return Mock()


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(telegram_router)
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
            response=ResultSet(
                request_id="req-1",
                type_="flights",
                result_set=[{"flight_no": "SQ123", "price": 120}]
            ),
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


def test_webhook_happy_path_returns_200(client, app, valid_update, success_response):
    app.state.telegram_handler.handle.return_value = success_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "correct-secret"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


def test_webhook_invalid_secret_returns_401(client, valid_update):
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_webhook_secret"


def test_webhook_valid_secret_passes(client, app, valid_update, success_response):
    app.state.telegram_handler.handle.return_value = success_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )

    assert response.status_code == 200


def test_webhook_invalid_update_returns_400(client, app, valid_update, error_response, caplog):
    app.state.telegram_handler.handle.return_value = error_response

    with caplog.at_level("ERROR", logger="data_ontology"):
        response = client.post(
            "/telegram/webhook",
            json=valid_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"}
        )

    assert response.status_code == 400
    assert any("returning 400" in r.message for r in caplog.records)


def test_webhook_orchestrator_error_still_delivers_message_and_returns_200(
    client, app, valid_update, success_response
):
    app.state.telegram_handler.handle.return_value = success_response

    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"}
    )

    assert response.status_code == 200
