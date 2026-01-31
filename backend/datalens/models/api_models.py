from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel

from datalens.models.result_models import QueryResult


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    """
    Successful API response.
    """
    status: str = "success"
    result: QueryResult
    summary: Optional[str] = None  # for later LLM-generated summaries


class ErrorResponse(BaseModel):
    """
    Standard error response returned by any failure stage.
    """
    status: str = "error"
    stage: str  # planner | grounding | compiler | executor | api
    error_code: str
    message: str