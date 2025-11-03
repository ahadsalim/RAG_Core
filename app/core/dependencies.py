"""
Core Dependencies
Shared dependencies for dependency injection
"""

from typing import AsyncGenerator
import redis.asyncio as redis
from functools import lru_cache

from app.config.settings import settings

# Redis client instance
_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """
    Get Redis client instance.
    
    Returns:
        Redis client
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            str(settings.redis_url),
            password=settings.redis_password,
            max_connections=settings.redis_max_connections,
            decode_responses=settings.redis_decode_responses,
            encoding="utf-8",
        )
    
    return _redis_client


async def close_redis_client():
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
