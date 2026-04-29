import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.requests import Request

from models.common import ErrorResponse
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
    graphdb_service = request.app.state.graphdb_service

    # ── Try graphdb pipeline first ────────────────────────────────
    if graphdb_service is not None:
        graphdb_result = await asyncio.to_thread(
            graphdb_service.ask, nlq_request.question
        )
        if graphdb_result is not None:
            return StreamingResponse(
                message_streamer([graphdb_result]), media_type="text/plain"
            )

    # ── Fall back to existing orchestrator chain ──────────────────
    orchestrator = request.app.state.orchestrator

    task = await asyncio.gather(
        asyncio.to_thread(
            handler_request,
            orchestrator=orchestrator,
            nlq_request=nlq_request,
        )
    )

    result = task[0]

    if isinstance(result, ErrorResponse):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(),
        )

    return StreamingResponse(message_streamer(result.data), media_type="text/plain")


def handler_request(orchestrator, nlq_request):
    return orchestrator.handle_question(nlq_request)


async def message_streamer(messages: list[str]):
    for message in messages:
        yield message
        await asyncio.sleep(0.5)
