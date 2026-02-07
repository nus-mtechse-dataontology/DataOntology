from typing import Optional
from pydantic import BaseModel

from app.models.results import QueryResult


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
