from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import NoResultFound

from services.auth.authentication_service import AuthenticationService


@pytest.fixture
def mock_accounts_dao():
    return Mock()


@pytest.fixture
def mock_jwt_handler():
    return Mock()


@pytest.fixture
def auth_service(mock_accounts_dao, mock_jwt_handler):
    service = AuthenticationService(mock_accounts_dao, mock_jwt_handler)
    return service


@pytest.fixture
def user_model():
    return SimpleNamespace(
        f_hashed_password="hashed",
        model_dump=lambda **kwargs: {
            "username": "test_user",
            "full_name": "Test User",
            "email": "user@example.com",
            "disabled": False,
        },
    )


def test_authenticate_user_success_returns_token(auth_service, mock_accounts_dao, mock_jwt_handler, user_model):
    mock_accounts_dao.get_user.return_value = user_model
    auth_service._password_hash = Mock()
    auth_service._password_hash.verify.return_value = True
    mock_jwt_handler.get_token.return_value = "token"

    result = auth_service.authenticate_user("test_user", "password")

    assert result["verified"] is True
    assert result["access_token"] == "token"
    assert result["token_type"] == "bearer"
    assert result["full_name"] == "Test User"
    mock_accounts_dao.get_user.assert_called_once_with("test_user")
    mock_jwt_handler.get_token.assert_called_once()


def test_authenticate_user_invalid_password_returns_failure(auth_service, mock_accounts_dao, user_model):
    mock_accounts_dao.get_user.return_value = user_model
    auth_service._password_hash = Mock()
    auth_service._password_hash.verify.return_value = False

    result = auth_service.authenticate_user("test_user", "bad-password")

    assert result["verified"] is False
    assert result["access_token"] is None
    assert result["token_type"] is None


def test_authenticate_user_missing_user_returns_failure(auth_service, mock_accounts_dao):
    mock_accounts_dao.get_user.side_effect = NoResultFound
    auth_service._password_hash = Mock()
    auth_service._password_hash.hash.return_value = "hashed"
    auth_service._password_hash.verify.return_value = False

    result = auth_service.authenticate_user("missing", "password")

    assert result["verified"] is False
    assert result["access_token"] is None
    assert result["token_type"] is None
