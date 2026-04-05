from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from models.common import ErrorDetails, ErrorResponse, SuccessResponse
from models.pipeline import NLQRequest


query_router = APIRouter(prefix="/query", tags=["query"])


@query_router.post(
    "/query",
    responses={
        status.HTTP_200_OK: {"description": "Query executed successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def query(nlq_request: NLQRequest, request: Request):
    orchestrator = request.app.state.orchestrator

    result = orchestrator.handle_question(nlq_request)

    if isinstance(result, ErrorResponse):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(),
    )
