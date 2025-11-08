"""
Multi-Layer Cache Manager
Implements a three-tier caching strategy for optimal performance
"""

from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import json
import hashlib
import pickle
from functools import lru_cache
import redis.asyncio as redis
from cachetools import TTLCache
import structlog

from app.config.settings import settings
from app.core.exceptions import CacheException, CacheConnectionError

logger = structlog.get_logger()


class MultiLayerCacheManager:
    """
    Three-tier caching system:
    
    1. Memory Cache (L1): Fastest, smallest capacity, shortest TTL
       - Uses TTLCache for automatic expiration
       - Ideal for frequently accessed data
       
    2. Redis Cache (L2): Fast, medium capacity, medium TTL
       - Distributed cache shared across instances
       - Good for session data and temporary results
       
    3. Database Cache (L3): Slower, large capacity, long TTL
       - PostgreSQL for semantic caching
       - Used for RAG query results
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        memory_maxsize: int = 1000,
        memory_ttl: int = 300,  # 5 minutes
        redis_ttl: int = 3600,  # 1 hour
    ):
        """
        Initialize multi-layer cache manager.
        
        Args:
            redis_client: Redis client instance
            memory_maxsize: Maximum items in memory cache
            memory_ttl: Memory cache TTL in seconds
            redis_ttl: Redis cache TTL in seconds
        """
        self.redis = redis_client
        self.redis_ttl = redis_ttl
        
        # L1: In-memory cache with TTL
        self.memory_cache = TTLCache(maxsize=memory_maxsize, ttl=memory_ttl)
        
        # Statistics
        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "db_hits": 0,
            "db_misses": 0
        }
    
    def _generate_key(self, prefix: str, identifier: str) -> str:
        """
        Generate a cache key.
        
        Args:
            prefix: Key prefix (e.g., 'query', 'user', 'embedding')
            identifier: Unique identifier
            
        Returns:
            Cache key string
        """
        return f"{prefix}:{identifier}"
    
    def _hash_query(self, query: str) -> str:
        """
        Generate a hash for a query string.
        
        Args:
            query: Query text
            
        Returns:
            SHA-256 hash
        """
        return hashlib.sha256(query.encode()).hexdigest()
    
    async def get(
        self,
        key: str,
        check_memory: bool = True,
        check_redis: bool = True
    ) -> Optional[Any]:
        """
        Get value from cache (checks all layers).
        
        Args:
            key: Cache key
            check_memory: Whether to check memory cache
            check_redis: Whether to check Redis cache
            
        Returns:
            Cached value or None
        """
        # L1: Check memory cache
        if check_memory and key in self.memory_cache:
            self.stats["memory_hits"] += 1
            logger.debug(f"Memory cache hit: {key}")
            return self.memory_cache[key]
        
        if check_memory:
            self.stats["memory_misses"] += 1
        
        # L2: Check Redis cache
        if check_redis:
            try:
                redis_value = await self.redis.get(key)
                if redis_value:
                    self.stats["redis_hits"] += 1
                    logger.debug(f"Redis cache hit: {key}")
                    
                    # Deserialize
                    value = pickle.loads(redis_value)
                    
                    # Promote to memory cache
                    if check_memory:
                        self.memory_cache[key] = value
                    
                    return value
                else:
                    self.stats["redis_misses"] += 1
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
                raise CacheConnectionError(f"Failed to read from Redis: {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        set_memory: bool = True,
        set_redis: bool = True
    ):
        """
        Set value in cache (writes to all layers).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            set_memory: Whether to set in memory cache
            set_redis: Whether to set in Redis cache
        """
        # L1: Set in memory cache
        if set_memory:
            self.memory_cache[key] = value
            logger.debug(f"Set memory cache: {key}")
        
        # L2: Set in Redis cache
        if set_redis:
            try:
                # Serialize value
                serialized = pickle.dumps(value)
                
                # Set with TTL
                cache_ttl = ttl or self.redis_ttl
                await self.redis.setex(key, cache_ttl, serialized)
                logger.debug(f"Set Redis cache: {key} (TTL: {cache_ttl}s)")
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
                raise CacheConnectionError(f"Failed to write to Redis: {e}")
    
    async def delete(self, key: str):
        """
        Delete value from all cache layers.
        
        Args:
            key: Cache key
        """
        # Delete from memory
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        # Delete from Redis
        try:
            await self.redis.delete(key)
            logger.debug(f"Deleted from cache: {key}")
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    async def clear_pattern(self, pattern: str):
        """
        Clear all keys matching a pattern (Redis only).
        
        Args:
            pattern: Key pattern (e.g., 'user:*')
        """
        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.redis.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Cleared cache pattern: {pattern}")
        except Exception as e:
            logger.error(f"Failed to clear pattern: {e}")
    
    async def get_or_set(
        self,
        key: str,
        factory_func,
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or compute and cache it.
        
        Args:
            key: Cache key
            factory_func: Async function to compute value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = await self.get(key)
        
        if value is not None:
            return value
        
        # Compute value
        value = await factory_func()
        
        # Cache it
        await self.set(key, value, ttl=ttl)
        
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = sum([
            self.stats["memory_hits"],
            self.stats["memory_misses"]
        ])
        
        memory_hit_rate = (
            self.stats["memory_hits"] / total_requests
            if total_requests > 0 else 0
        )
        
        redis_requests = sum([
            self.stats["redis_hits"],
            self.stats["redis_misses"]
        ])
        
        redis_hit_rate = (
            self.stats["redis_hits"] / redis_requests
            if redis_requests > 0 else 0
        )
        
        return {
            "memory": {
                "hits": self.stats["memory_hits"],
                "misses": self.stats["memory_misses"],
                "hit_rate": memory_hit_rate,
                "size": len(self.memory_cache),
                "maxsize": self.memory_cache.maxsize
            },
            "redis": {
                "hits": self.stats["redis_hits"],
                "misses": self.stats["redis_misses"],
                "hit_rate": redis_hit_rate
            },
            "overall_hit_rate": (
                (self.stats["memory_hits"] + self.stats["redis_hits"]) /
                (total_requests if total_requests > 0 else 1)
            )
        }
    
    def reset_stats(self):
        """Reset cache statistics."""
        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "db_hits": 0,
            "db_misses": 0
        }


class QueryCacheManager(MultiLayerCacheManager):
    """
    Specialized cache manager for RAG queries.
    
    Implements semantic caching for similar queries.
    """
    
    async def get_query_cache(
        self,
        query: str,
        filters: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached query result.
        
        Args:
            query: Query text
            filters: Optional filters
            
        Returns:
            Cached response or None
        """
        # Generate cache key
        cache_key = self._generate_query_key(query, filters)
        
        # Get from cache
        return await self.get(cache_key)
    
    async def set_query_cache(
        self,
        query: str,
        response: Dict[str, Any],
        filters: Optional[Dict] = None,
        ttl: int = 3600
    ):
        """
        Cache query result.
        
        Args:
            query: Query text
            response: Query response
            filters: Optional filters
            ttl: Time to live in seconds
        """
        # Generate cache key
        cache_key = self._generate_query_key(query, filters)
        
        # Add metadata
        cache_data = {
            "query": query,
            "response": response,
            "filters": filters,
            "cached_at": datetime.utcnow().isoformat(),
            "ttl": ttl
        }
        
        # Set in cache
        await self.set(cache_key, cache_data, ttl=ttl)
    
    def _generate_query_key(
        self,
        query: str,
        filters: Optional[Dict] = None
    ) -> str:
        """
        Generate cache key for a query.
        
        Args:
            query: Query text
            filters: Optional filters
            
        Returns:
            Cache key
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Include filters in key
        if filters:
            filter_str = json.dumps(filters, sort_keys=True)
            key_input = f"{normalized_query}:{filter_str}"
        else:
            key_input = normalized_query
        
        # Hash the key
        query_hash = self._hash_query(key_input)
        
        return self._generate_key("query", query_hash)


# Singleton instance (will be initialized in app startup)
_cache_manager: Optional[MultiLayerCacheManager] = None


async def get_cache_manager() -> MultiLayerCacheManager:
    """
    Get the global cache manager instance.
    
    Returns:
        Cache manager instance
    """
    global _cache_manager
    
    if _cache_manager is None:
        from app.core.dependencies import get_redis_client
        redis_client = await get_redis_client()
        _cache_manager = MultiLayerCacheManager(redis_client)
    
    return _cache_manager
