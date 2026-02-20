"""Shared contracts/models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass(frozen=True)
class QueryRequest:
    nlq: str
    include_debug: bool = False


@dataclass(frozen=True)
class QueryPlan:
    intent: Optional[str]
    params: Dict[str, Any] = field(default_factory=dict)
    missing_params: List[str] = field(default_factory=list)
    follow_up_question: Optional[str] = None
    confidence: Optional[float] = None

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "QueryPlan":
        intent = payload.get("intent")
        if intent is not None and not isinstance(intent, str):
            raise ValueError("Query plan field 'intent' must be a string or null")

        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("Query plan field 'params' must be an object")

        missing_params = payload.get("missing_params", [])
        if missing_params is None:
            missing_params = []
        if not isinstance(missing_params, list) or any(not isinstance(x, str) for x in missing_params):
            raise ValueError("Query plan field 'missing_params' must be a list of strings")

        follow_up_question = payload.get("follow_up_question")
        if follow_up_question is not None and not isinstance(follow_up_question, str):
            raise ValueError("Query plan field 'follow_up_question' must be a string or null")

        confidence = payload.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError) as exc:
                raise ValueError("Query plan field 'confidence' must be numeric or null") from exc

        return QueryPlan(
            intent=intent,
            params=dict(params),
            missing_params=list(missing_params),
            follow_up_question=follow_up_question,
            confidence=confidence,
        )


@dataclass(frozen=True)
class CompiledQuery:
    intent: str
    sql: str
    bound_params: Dict[str, Any]


@dataclass(frozen=True)
class ExecutionResult:
    rows: List[Dict[str, Any]]


@dataclass(frozen=True)
class QueryResponse:
    status: Literal["clarification_needed", "success"]
    intent: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    missing_params: List[str] = field(default_factory=list)
    follow_up_question: Optional[str] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    sql: Optional[str] = None