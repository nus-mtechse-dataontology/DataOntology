from unittest.mock import Mock

import pytest
from sqlalchemy.exc import NoResultFound

from models.register_model import RegisterModel
from services.registration.registration_service import RegistrationService


@pytest.fixture
def mock_registration_dao():
    return Mock()


@pytest.fixture
def mock_accounts_dao():
    return Mock()


@pytest.fixture
def registration_service(mock_registration_dao, mock_accounts_dao):
    return RegistrationService(mock_registration_dao, mock_accounts_dao)


@pytest.fixture
def register_model():
    return RegisterModel(
        username="new_user",
        password="secret",
        email="new@example.com",
        full_name="New User",
    )


def test_register_user_new_user_creates_account(
    registration_service,
    mock_registration_dao,
    mock_accounts_dao,
    register_model,
):
    mock_accounts_dao.get_user.side_effect = NoResultFound
    registration_service._password_hash = Mock()
    registration_service._password_hash.hash.return_value = "hashed"

    result = registration_service.register_user(register_model)

    assert result["status"] == 0
    assert result["message"] == "User registered"
    assert result["username"] == "new_user"
    assert result["full_name"] == "New User"
    mock_registration_dao.register_user.assert_called_once()


def test_register_user_existing_user_returns_conflict(
    registration_service,
    mock_accounts_dao,
    register_model,
):
    mock_accounts_dao.get_user.return_value = Mock()

    result = registration_service.register_user(register_model)

    assert result["status"] == 1
    assert result["message"] == "User already exists"
    assert result["username"] == "new_user"


def test_register_user_empty_username_edge_case(
    registration_service,
    mock_accounts_dao,
):
    user = RegisterModel(username="", password="secret")
    mock_accounts_dao.get_user.side_effect = NoResultFound
    registration_service._password_hash = Mock()
    registration_service._password_hash.hash.return_value = "hashed"
    
    result = registration_service.register_user(user)

    assert result["status"] == 0
    assert result["username"] == ""
