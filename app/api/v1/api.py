"""
API Router Configuration
Main API router combining all endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    query,
    users,
    sync,
    admin,
    health,
    embedding
)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    query.router,
    prefix="/query",
    tags=["Query Processing"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["User Management"]
)

api_router.include_router(
    sync.router,
    prefix="/sync",
    tags=["Synchronization"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Administration"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health Check"]
)

api_router.include_router(
    embedding.router,
    prefix="",
    tags=["Embeddings"]
)
