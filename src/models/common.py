from typing import Any, Dict, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ErrorDetails(BaseModel):
    code: str
    message: str
    component: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    request_id: str
    status: Literal["ERROR"] = "ERROR"
    error: ErrorDetails


class SuccessResponse(BaseModel, Generic[T]):
    request_id: str
    status: Literal["SUCCESS"] = "SUCCESS"
    data: T
