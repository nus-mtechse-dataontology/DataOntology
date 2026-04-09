from datetime import datetime
import logging
import os
import signal
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.background import BackgroundTasks


status_router = APIRouter(prefix='/actuator', tags=["Status"])
log = logging.getLogger("data_ontology")


@status_router.get('/health/liveness')
async def liveness():
    return JSONResponse(
        status_code=200,
        content={
            'msg': 'alive',
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'datetime_timestamp': int(datetime.now().timestamp()),
            'uuid': str(uuid4())
        }
    )

@status_router.get('/health/readiness')
async def readiness():
    return JSONResponse(
        status_code=200,
        content={
            'msg': 'ready',
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'datetime_timestamp': int(datetime.now().timestamp()),
            'uuid': str(uuid4())
        }
    )


@status_router.post('/shutdown/')
async def shutdown(request: Request, background_tasks: BackgroundTasks):
    log.info("Status: Shutdown initiated...")
    background_tasks.add_task(shutdown_server)

    return JSONResponse(
        status_code=200,
        content={
            'msg': 'shutting down',
            'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'datetime_timestamp': int(datetime.now().timestamp()),
            'uuid': str(uuid4())
        }
    )


def shutdown_server():
    try:
        log.info("Status: Attempting to shutdown server gracefully... ")
        os.kill(os.getpid(), signal.SIGTERM)

    except Exception as e:
        log.warning("Status: Unable to gracefully shutdown server, executing force shutdown... ")
        log.warning(e)
        os.kill(os.getpid(), signal.SIGKILL)
