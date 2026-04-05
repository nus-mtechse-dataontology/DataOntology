from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class NLQRequest(BaseModel):
    request_id: str = "unknown"
    request_type: Literal[
        "request",
        "prompt",
        "llm",
        "syntactic",
        "semantics",
        "sql_compile",
        "sql_executor",
        "result"
    ] = "request"
    question: str = ""
    system_message: str = ""
    user_message: str = ""
    raw_response_text: str = ""
    query_plan: QueryPlan | None = None
    compiled_sql: CompiledSQL | None = None
    result_set: ResultSet | None = None

class PromptRequest(BaseModel):
    request_id: str
    question: str
    prompt_template: str
    semantic_model: Dict[str, Any]


class PromptBundle(BaseModel):
    system_message: str
    user_message: str


class LLMRawResponse(BaseModel):
    raw_response_text: str


class QueryPlan(BaseModel):
    request_id: str
    intent: str
    parameters: Dict[str, Any]
    missing_params: List[str] = Field(default_factory=list)
    follow_up_question: Optional[str] = None
    confidence: float


class CompiledSQL(BaseModel):
    request_id: str
    sql: str
    bound_params: Dict[str, Any] = Field(default_factory=dict)


class Row(BaseModel):
    data: Dict[str, Any]


class ResultSet(BaseModel):
    request_id: str
    result_set: List[Row] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    request_id: str
    response: str
