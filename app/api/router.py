from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router

router = APIRouter()
router.include_router(health_router)
router.include_router(query_router)
