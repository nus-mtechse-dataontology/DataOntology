from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CompiledQuery(BaseModel):
    """
    Output of the deterministic compiler.
    """
    sql: str
    params: List[Any] = Field(default_factory=list)


class QueryResult(BaseModel):
    """
    Output of the executor. Keep it simple for Sprint 1.

    rows: list of objects (dict-like) so the API can return JSON easily.
    """
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_ms: Optional[int] = None
