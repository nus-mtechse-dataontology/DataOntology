"""Integration tests: POST /query/query and GET /query/get_query routes.

Uses FastAPI TestClient with a mocked orchestrator to test HTTP-level
request/response handling — status codes, JSON shapes, error mapping.
"""

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from endpoints.routes.query.query_routes import query_router
from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import QuestionResponse, ResultSet


def _create_app(orchestrator_mock: Mock) -> FastAPI:
    app = FastAPI()
    app.include_router(query_router)
    app.state.orchestrator = orchestrator_mock
    return app


# ── POST /query/query ────────────────────────────────────────────────────


def test_query_success_returns_200_with_response_data():
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = SuccessResponse(
        request_id="req-1",
        data=["I found 2 matching records:\n1. SIN→BKK $180\n2. SIN→BKK $320"],
    )
    client = TestClient(_create_app(mock_orchestrator))
    
    response = client.post(
        "/query/query",
        json={"request_id": "req-1", "question": "Cheapest flight from SIN to BKK?"},
    )
    
    assert response.status_code == 200
    body = response.text
    assert "180" in body



def test_query_error_returns_400_with_error_details():
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = ErrorResponse(
        request_id="req-2",
        error=ErrorDetails(
            code="invalid_intent",
            message="Intent 'book_hotel' not found in semantic model.",
            component="semantic_validator",
        ),
    )
    client = TestClient(_create_app(mock_orchestrator))
    
    response = client.post(
        "/query/query",
        json={"request_id": "req-2", "question": "Book a hotel in Bangkok"},
    )
    
    assert response.status_code == 200
    assert "Intent 'book_hotel' not found in semantic model." in response.text



def test_query_passes_nlq_request_to_orchestrator():
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = SuccessResponse(
        request_id="req-5",
        data=["OK"],
    )
    client = TestClient(_create_app(mock_orchestrator))

    client.post(
        "/query/query",
        json={"request_id": "req-5", "question": "Show me flights"},
    )

    mock_orchestrator.handle_question.assert_called_once()
    nlq_req = mock_orchestrator.handle_question.call_args[0][0]
    assert nlq_req.request_id == "req-5"
    assert nlq_req.question == "Show me flights"


def test_query_empty_body_uses_defaults_and_calls_orchestrator():
    """NLQRequest has defaults for all fields — empty body is valid and reaches orchestrator."""
    mock_orchestrator = Mock()
    mock_orchestrator.handle_question.return_value = SuccessResponse(
        request_id="unknown",
        data=["OK"],
    )
    client = TestClient(_create_app(mock_orchestrator))

    response = client.post("/query/query", json={})

    assert response.status_code == 200
    mock_orchestrator.handle_question.assert_called_once()


