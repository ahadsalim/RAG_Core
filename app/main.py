"""
Core System - Main Application Entry Point
FastAPI application setup with middleware, routers, and event handlers
"""

from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.config.settings import settings
from app.api.v1.api import api_router
from app.core.dependencies import get_redis_client
from app.db.session import init_db, close_db
from app.services.qdrant_service import QdrantService
from app.utils.logging import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Core System", version=settings.app_version, environment=settings.environment)
    
    try:
        # Initialize database connections
        await init_db()
        logger.info("Database connections initialized")
        
        # Initialize Qdrant
        qdrant_service = QdrantService()
        await qdrant_service.init_collection()
        logger.info("Qdrant vector database initialized")
        
        # Initialize Redis
        redis = await get_redis_client()
        await redis.ping()
        logger.info("Redis cache initialized")
        
        logger.info("Core System started successfully")
        
    except Exception as e:
        logger.error("Failed to initialize application", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Core System")
    
    try:
        # Close database connections
        await close_db()
        
        # Close Redis
        redis = await get_redis_client()
        await redis.close()
        
        logger.info("Core System shutdown complete")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RAG Engine and AI Processing System for Legal Document Q&A",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


# Add middleware
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted host (security)
if settings.is_production:
    allowed_hosts = {"localhost", "127.0.0.1", "10.10.10.20", "10.10.10.30", "10.10.10.40", "10.10.10.50"}
    if settings.domain_name:
        allowed_hosts.add(settings.domain_name)
        parts = settings.domain_name.split(".")
        if len(parts) >= 2:
            base = ".".join(parts[-2:])
            allowed_hosts.add(base)
            allowed_hosts.add(f"*.{base}")
    else:
        allowed_hosts.update({"yourdomain.com", "*.yourdomain.com"})
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(allowed_hosts)
    )

# Include API routers
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with system information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "healthy",
        "docs": "/docs" if settings.debug else None,
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring."""
    health_status = {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "services": {}
    }
    
    try:
        # Check database
        from app.db.session import get_session
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        # Check Redis
        redis = await get_redis_client()
        await redis.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        # Check Qdrant
        qdrant_service = QdrantService()
        if await qdrant_service.health_check():
            health_status["services"]["qdrant"] = "healthy"
        else:
            health_status["services"]["qdrant"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["qdrant"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    if settings.debug:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "path": request.url.path
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred"}
    )


# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 error handler."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": "Endpoint not found",
            "path": request.url.path
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["default"],
            },
        }
    )
