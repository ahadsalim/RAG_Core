"""
Health Check API Endpoints
Simple health check endpoints for monitoring
"""

from fastapi import APIRouter
from app.config.settings import settings

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "core",
        "version": settings.app_version
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    # In production, check if all services are ready
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"alive": True}
