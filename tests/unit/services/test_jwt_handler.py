"""Unit tests for JWTHandler."""

import time

import jwt
import pytest

from services.auth.jwt_handler import JWTHandler

SECRET = "test-secret"
ALGO = "HS256"


@pytest.fixture
def handler():
    return JWTHandler(secret=SECRET, expire_mins=15, algo=ALGO)


# ── get_token ─────────────────────────────────────────────────────────────


def test_get_token_returns_non_empty_string(handler):
    token = handler.get_token({"sub": "user-1"})

    assert isinstance(token, str)
    assert len(token) > 0


def test_get_token_encodes_payload(handler):
    token = handler.get_token({"sub": "user-1", "role": "admin"})
    decoded = jwt.decode(token, SECRET, algorithms=[ALGO])

    assert decoded["sub"] == "user-1"
    assert decoded["role"] == "admin"


def test_get_token_includes_expiry(handler):
    token = handler.get_token({"sub": "user-1"})
    decoded = jwt.decode(token, SECRET, algorithms=[ALGO])

    assert "exp" in decoded


def test_get_token_does_not_mutate_input_data(handler):
    data = {"sub": "user-1"}
    handler.get_token(data)

    assert "exp" not in data


# ── verify_token ──────────────────────────────────────────────────────────


def test_verify_token_returns_payload_for_valid_token(handler):
    token = handler.get_token({"sub": "user-1"})
    payload = handler.verify_token(token)

    assert payload["sub"] == "user-1"


def test_verify_token_raises_on_expired_token():
    expired_handler = JWTHandler(secret=SECRET, expire_mins=0, algo=ALGO)
    token = expired_handler.get_token({"sub": "user-1"})
    time.sleep(1)

    with pytest.raises(jwt.ExpiredSignatureError):
        expired_handler.verify_token(token)


def test_verify_token_raises_on_tampered_token(handler):
    token = handler.get_token({"sub": "user-1"})
    tampered = token[:-4] + "xxxx"

    with pytest.raises(jwt.InvalidTokenError):
        handler.verify_token(tampered)


def test_verify_token_raises_on_wrong_secret(handler):
    token = handler.get_token({"sub": "user-1"})
    wrong_handler = JWTHandler(secret="wrong-secret", expire_mins=15, algo=ALGO)

    with pytest.raises(jwt.InvalidTokenError):
        wrong_handler.verify_token(token)
