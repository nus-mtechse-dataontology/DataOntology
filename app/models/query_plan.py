from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    """
    Untrusted query plan produced by the planner (LLM or stub).
    Must be validated and grounded before use.
    """

    source: str = Field(..., description="Logical data source, e.g. 'flights'")
    select: List[str] = Field(..., description="Fields or metrics to select")
    filters: Optional[Dict[str, str]] = Field(
        default=None,
        description="Simple equality filters, e.g. {'destination': 'Tokyo'}",
    )
    group_by: Optional[List[str]] = Field(
        default=None,
        description="Optional grouping fields",
    )


class ValidatedQueryPlan(QueryPlan):
    """
    A query plan that has passed schema, semantic, and security checks.
    """
    pass
