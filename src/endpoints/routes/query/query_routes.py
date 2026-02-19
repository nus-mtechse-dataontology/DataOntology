from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.requests import Request


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