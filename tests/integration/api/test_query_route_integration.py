"""Integration tests: POST /query/query and GET /query/get_query routes.

Uses FastAPI TestClient with a mocked orchestrator to test HTTP-level
request/response handling — status codes, JSON shapes, error mapping.
"""

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.query.query_routes import query_router
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse


def _create_app(orchestrator_mock: Mock) -> FastAPI:
    """Create a minimal FastAPI app with the query router and a mocked orchestrator."""
    app = FastAPI()
    app.include_router(query_router)
    app.state.orchestrator = orchestrator_mock
    return app


# ── POST /query/query ────────────────────────────────────────────────────


def test_query_success_returns_200_with_response_data():
    """Valid NLQ request → orchestrator returns SuccessResponse → 200 OK."""
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = SuccessResponse(
        request_id="req-1",
        data=QuestionResponse(
            request_id="req-1",
            response="I found 2 matching records:\n1. SIN→BKK $180\n2. SIN→BKK $320",
        ),
    )
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.post(
        "/query/query",
        json={"request_id": "req-1", "question": "Cheapest flight from SIN to BKK?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["request_id"] == "req-1"
    assert "180" in body["data"]["response"]


def test_query_error_returns_400_with_error_details():
    """Orchestrator returns ErrorResponse → 400 Bad Request."""
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = ErrorResponse(
        request_id="req-2",
        error=ErrorDetails(
            code="invalid_intent",
            message="Intent 'book_hotel' not found in semantic model.",
            component="semantic_validator",
        ),
    )
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.post(
        "/query/query",
        json={"request_id": "req-2", "question": "Book a hotel in Bangkok"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "ERROR"
    assert body["request_id"] == "req-2"
    assert body["error"]["code"] == "invalid_intent"
    assert body["error"]["component"] == "semantic_validator"


def test_query_missing_question_returns_422_validation_error():
    """Request body missing 'question' field → FastAPI returns 422."""
    mock_orchestrator = Mock()
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.post(
        "/query/query",
        json={"request_id": "req-3"},  # missing 'question'
    )

    assert response.status_code == 422
    mock_orchestrator.handle_question.assert_not_called()


def test_query_missing_request_id_returns_422_validation_error():
    """Request body missing 'request_id' field → FastAPI returns 422."""
    mock_orchestrator = Mock()
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.post(
        "/query/query",
        json={"question": "Cheapest flight?"},  # missing 'request_id'
    )

    assert response.status_code == 422
    mock_orchestrator.handle_question.assert_not_called()


def test_query_empty_body_returns_422_validation_error():
    """Empty JSON body → FastAPI returns 422."""
    mock_orchestrator = Mock()
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.post("/query/query", json={})

    assert response.status_code == 422
    mock_orchestrator.handle_question.assert_not_called()


def test_query_passes_nlq_request_to_orchestrator():
    """Verify the endpoint constructs NLQRequest correctly and passes it."""
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = SuccessResponse(
        request_id="req-5",
        data=QuestionResponse(request_id="req-5", response="OK"),
    )
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    client.post(
        "/query/query",
        json={"request_id": "req-5", "question": "Show me flights"},
    )

    mock_orchestrator.handle_question.assert_called_once()
    nlq_req = mock_orchestrator.handle_question.call_args[0][0]
    assert nlq_req.request_id == "req-5"
    assert nlq_req.question == "Show me flights"


# ── GET /query/get_query ─────────────────────────────────────────────────


def test_get_query_returns_200_with_health_info():
    """GET /query/get_query → 200 with msg, datetime, uuid."""
    mock_orchestrator = Mock()
    app = _create_app(mock_orchestrator)
    client = TestClient(app)

    response = client.get("/query/get_query")

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "Query Route"
    assert "datetime" in body
    assert "uuid" in body
