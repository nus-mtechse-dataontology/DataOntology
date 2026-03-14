"""Syntactic schema for LLM query-plan output."""

from pydantic import BaseModel, Field


class QueryPlanPayload(BaseModel):
    intent: str
    parameters: dict
    missing_params: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None
    confidence: float
