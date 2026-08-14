from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.mobile.router import api_router as mobile_router
from app.api.v1.superadmin.router import api_router as superadmin_router

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(superadmin_router, prefix="/superadmin")
api_router.include_router(mobile_router, prefix="/mobile")
