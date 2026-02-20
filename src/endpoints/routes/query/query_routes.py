from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from models.requests import QueryRequest
from models.responses import ErrorResponse, QueryResponse


query_router = APIRouter(prefix="/query", tags=["query"])


@query_router.get("/get_query")
async def get_query(request: Request):
    return JSONResponse(
        status_code=200,
        content={
            'msg': 'Query Route',
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'datetime_timestamp': int(datetime.now().timestamp()),
            'uuid': str(uuid4())
        }
    )


@query_router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_501_NOT_IMPLEMENTED: {"model": ErrorResponse},
    },
)
async def query(request: QueryRequest):
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
