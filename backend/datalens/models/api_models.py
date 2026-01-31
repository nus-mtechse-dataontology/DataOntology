from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str


class ErrorResponse(BaseModel):
    status: str = "error"
    stage: str  # e.g. "planner" | "grounding" | "compiler" | "executor"
    error_code: str
    message: str
