from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NLQRequest(BaseModel):
    request_id: str
    question: str


class PromptRequest(BaseModel):
    request_id: str
    question: str
    prompt_template: str
    semantic_model: Dict[str, Any]


class PromptBundle(BaseModel):
    request_id: str
    system_message: str
    user_message: str


class LLMRawResponse(BaseModel):
    request_id: str
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
