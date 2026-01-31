"""
API Layer tests (FastAPI routes)

Goal in Sprint 1:
- Validate request/response contracts at the HTTP boundary.
- Ensure errors are returned in a consistent shape.

Start with these tests:
1) Valid request:
   - POST /query with {"query": "..."} returns 200
2) Invalid request:
   - missing "query" or empty string returns 422 (Pydantic validation)
3) Error mapping:
   - when orchestrator returns ErrorResponse, API returns HTTP 400/500 appropriately
4) Contract check:
   - response JSON conforms to either success model (later) or ErrorResponse
"""
import pytest


def test_placeholder_api_query():
    # TODO Sprint 1: implement with FastAPI TestClient + /query route
    assert True
