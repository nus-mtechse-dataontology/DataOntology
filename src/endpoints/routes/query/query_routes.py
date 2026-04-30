import asyncio

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
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
        return StreamingResponse(message_streamer([result.error.message]), media_type="text/plain")
    
    return StreamingResponse(message_streamer(result.data), media_type="text/plain")


def handler_request(orchestrator, nlq_request):
    return orchestrator.handle_question(nlq_request)


async def message_streamer(messages: list[str]):
    for message in messages:
        yield message
        await asyncio.sleep(0.5)
