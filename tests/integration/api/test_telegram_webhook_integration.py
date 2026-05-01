import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

from endpoints.routes.telegram.telegram_routes import telegram_router
from models.common import SuccessResponse, ErrorResponse, ErrorDetails
from models.pipeline import QuestionResponse, ResultSet
from models.telegram_model import Update, Message, Chat, User

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(telegram_router)
    app.state.configured_secret = "correct-secret"
    
    # We mock the handler because it's a complex object, 
    # but for a true integration test we could wire it up.
    # For now, let's make these tests pass by mocking the handler's behavior.
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
            date=int(datetime.now().timestamp()),
            from_user=User(id=1, is_bot=False, first_name="test"),
            text="What are my top holdings?",
            chat=Chat(id=123456, type="private", first_name="test"),
        )
    ).model_dump(by_alias=True)

def test_telegram_webhook_rejects_invalid_secret(client, valid_update):
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "wrong-secret"}
    )
    
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_webhook_secret"

def test_telegram_webhook_returns_200_and_delivery_status(client, app, valid_update):
    # Mock the handler to return a success response
    app.state.telegram_handler.handle.return_value = SuccessResponse(
        request_id="req-1",
        data={"chat_id": 123456, "delivered": True}
    )
    
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "correct-secret"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["data"]["chat_id"] == 123456
    assert data["data"]["delivered"] is True

def test_telegram_webhook_returns_400_on_handler_error(client, app, valid_update):
    # Mock the handler to return an error response
    app.state.telegram_handler.handle.return_value = ErrorResponse(
        request_id="req-err",
        error=ErrorDetails(
            code="telegram_webhook_failed",
            message="Unable to handle request",
            component="telegram_webhook"
        )
    )
    
    response = client.post(
        "/telegram/webhook",
        json=valid_update,
        headers={"x-telegram-bot-api-secret-token": "correct-secret"}
    )
    
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "telegram_webhook_failed"
