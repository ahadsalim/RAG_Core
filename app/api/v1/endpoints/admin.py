"""
Administration API Endpoints
Admin endpoints for system management and monitoring
"""

from typing import Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text as sa_text
from pydantic import BaseModel
import structlog

from app.db.session import get_db
from app.models.user import UserProfile, Conversation, Message, QueryCache
from app.services.qdrant_service import QdrantService
from app.core.dependencies import get_redis_client
from app.config.settings import settings

logger = structlog.get_logger()
router = APIRouter()


# Response Models
class SystemStats(BaseModel):
    """System statistics response."""
    total_users: int
    active_users_24h: int
    total_conversations: int
    total_messages: int
    total_tokens_used: int
    cache_hit_rate: float
    qdrant_vectors: int
    avg_response_time_ms: float


class CacheStats(BaseModel):
    """Cache statistics response."""
    redis_keys: int
    redis_memory_mb: float
    query_cache_entries: int
    cache_hit_rate: float
    most_cached_queries: list[Dict[str, Any]]


# Admin authentication
async def verify_admin_access(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify admin access using X-API-Key header."""
    # In production, implement proper admin authentication / dedicated admin key
    if x_api_key not in {settings.ingest_api_key, settings.users_api_key}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin access required",
        )
    return x_api_key


# System statistics
@router.get("/stats", response_model=SystemStats)
async def get_system_statistics(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_access)
):
    """Get overall system statistics."""
    try:
        # User statistics
        total_users = await db.scalar(
            select(func.count()).select_from(UserProfile)
        )
        
        # Active users in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users = await db.scalar(
            select(func.count()).select_from(UserProfile)
            .where(UserProfile.last_active_at > yesterday)
        )
        
        # Conversation and message statistics
        total_conversations = await db.scalar(
            select(func.count()).select_from(Conversation)
        )
        
        total_messages = await db.scalar(
            select(func.count()).select_from(Message)
        )
        
        # Token usage
        total_tokens = await db.scalar(
            select(func.sum(UserProfile.total_tokens_used))
            .select_from(UserProfile)
        ) or 0
        
        # Average response time
        avg_response_time = await db.scalar(
            select(func.avg(Message.processing_time_ms))
            .select_from(Message)
            .where(Message.processing_time_ms.is_not(None))
        ) or 0
        
        # Cache statistics
        cache_hits = await db.scalar(
            select(func.sum(QueryCache.hit_count))
            .select_from(QueryCache)
        ) or 0
        
        total_queries = await db.scalar(
            select(func.sum(UserProfile.total_query_count))
            .select_from(UserProfile)
        ) or 1
        
        cache_hit_rate = cache_hits / total_queries if total_queries > 0 else 0
        
        # Qdrant statistics
        qdrant_service = QdrantService()
        qdrant_info = await qdrant_service.get_collection_info()
        
        return SystemStats(
            total_users=total_users,
            active_users_24h=active_users,
            total_conversations=total_conversations,
            total_messages=total_messages,
            total_tokens_used=total_tokens,
            cache_hit_rate=cache_hit_rate,
            qdrant_vectors=qdrant_info.get("points_count", 0),
            avg_response_time_ms=avg_response_time
        )
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


# Cache management
@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_statistics(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_access)
):
    """Get cache statistics and information."""
    try:
        redis = await get_redis_client()
        
        # Redis statistics
        info = await redis.info()
        redis_keys = await redis.dbsize()
        redis_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
        
        # Query cache statistics
        cache_entries = await db.scalar(
            select(func.count()).select_from(QueryCache)
        )
        
        # Most cached queries
        stmt = (
            select(
                QueryCache.query_text,
                QueryCache.hit_count,
                QueryCache.last_hit_at
            )
            .order_by(QueryCache.hit_count.desc())
            .limit(10)
        )
        
        result = await db.execute(stmt)
        most_cached = [
            {
                "query": row.query_text[:100],
                "hits": row.hit_count,
                "last_hit": row.last_hit_at.isoformat() if row.last_hit_at else None
            }
            for row in result
        ]
        
        # Calculate cache hit rate
        total_hits = await db.scalar(
            select(func.sum(QueryCache.hit_count))
            .select_from(QueryCache)
        ) or 0
        
        total_queries = await db.scalar(
            select(func.sum(UserProfile.total_query_count))
            .select_from(UserProfile)
        ) or 1
        
        cache_hit_rate = total_hits / total_queries if total_queries > 0 else 0
        
        return CacheStats(
            redis_keys=redis_keys,
            redis_memory_mb=redis_memory_mb,
            query_cache_entries=cache_entries,
            cache_hit_rate=cache_hit_rate,
            most_cached_queries=most_cached
        )
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


# Clear cache
@router.post("/cache/clear")
async def clear_cache(
    cache_type: str = Query(..., pattern="^(redis|query|all)$"),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_access)
):
    """Clear cache by type."""
    try:
        cleared = {"redis": False, "query": False}
        
        if cache_type in ["redis", "all"]:
            redis = await get_redis_client()
            await redis.flushdb()
            cleared["redis"] = True
        
        if cache_type in ["query", "all"]:
            await db.execute(
                sa_text("DELETE FROM query_cache WHERE expires_at < NOW()")
            )
            await db.commit()
            cleared["query"] = True
        
        return {
            "status": "success",
            "cleared": cleared
        }
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


# User management
@router.get("/users")
async def list_users(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_access)
):
    """List all users with filtering options."""
    try:
        stmt = select(UserProfile)
        
        stmt = stmt.order_by(UserProfile.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        return [
            {
                "id": str(user.id),
                "external_user_id": user.external_user_id,
                "username": user.username,
                "email": user.email,
                "total_queries": user.total_query_count,
                "total_tokens_used": user.total_tokens_used,
                "last_active": user.last_active_at,
                "created_at": user.created_at
            }
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


# NOTE: update_user_tier endpoint removed.
# Subscription/tier management is handled entirely by the Users system.
# See: Users system /srv/backend/subscriptions/models.py


# Optimize Qdrant
@router.post("/qdrant/optimize")
async def optimize_qdrant(
    admin: str = Depends(verify_admin_access)
):
    """Optimize Qdrant collection for better performance."""
    try:
        qdrant_service = QdrantService()
        await qdrant_service.optimize_collection()
        
        return {
            "status": "success",
            "message": "Qdrant optimization initiated"
        }
        
    except Exception as e:
        logger.error(f"Failed to optimize Qdrant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize Qdrant"
        )


# System health check
@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(verify_admin_access)
):
    """Get detailed health check of all services."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        health["services"]["database"] = "healthy"
    except Exception as e:
        health["services"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    # Check Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        health["services"]["redis"] = "healthy"
    except Exception as e:
        health["services"]["redis"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    # Check Qdrant
    try:
        qdrant_service = QdrantService()
        if await qdrant_service.health_check():
            health["services"]["qdrant"] = "healthy"
        else:
            health["services"]["qdrant"] = "unhealthy"
            health["status"] = "degraded"
    except Exception as e:
        health["services"]["qdrant"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    return health
