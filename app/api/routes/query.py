from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.models.requests import QueryRequest
from app.models.responses import ErrorResponse, QueryResponse

router = APIRouter()


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_501_NOT_IMPLEMENTED: {"model": ErrorResponse},
    },
)
def query(request: QueryRequest):
    _ = request
    error = ErrorResponse(
        stage="api",
        error_code="not_implemented",
        message="Query endpoint not implemented",
    )
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=error.model_dump(),
    )
