"""
Advanced Rate Limiter
Implements sliding window rate limiting with multiple time windows
"""

from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
import structlog

from app.config.settings import settings
from app.core.exceptions import (
    RateLimitException,
    MinuteLimitExceeded,
    HourLimitExceeded,
    DailyLimitExceeded
)

logger = structlog.get_logger()


class RateLimiter:
    """
    Advanced rate limiter using Redis with sliding window algorithm.
    
    Supports multiple time windows:
    - Per-minute limits
    - Per-hour limits
    - Per-day limits
    
    Uses Redis sorted sets for efficient sliding window implementation.
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        
    async def check_rate_limit(
        self,
        user_id: str,
        limit_per_minute: int = 10,
        limit_per_hour: int = 100,
        limit_per_day: int = 1000
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if user has exceeded rate limits.
        
        Args:
            user_id: User identifier
            limit_per_minute: Maximum requests per minute
            limit_per_hour: Maximum requests per hour
            limit_per_day: Maximum requests per day
            
        Returns:
            Tuple of (is_allowed, limit_type, retry_after_seconds)
            
        Raises:
            RateLimitException: If rate limit is exceeded
        """
        now = datetime.utcnow()
        
        # Check minute limit
        minute_allowed, minute_retry = await self._check_window(
            user_id=user_id,
            window_name="minute",
            window_seconds=60,
            limit=limit_per_minute,
            now=now
        )
        
        if not minute_allowed:
            raise MinuteLimitExceeded(
                message=f"Rate limit exceeded: {limit_per_minute} requests per minute",
                retry_after=minute_retry,
                limit_type="minute"
            )
        
        # Check hour limit
        hour_allowed, hour_retry = await self._check_window(
            user_id=user_id,
            window_name="hour",
            window_seconds=3600,
            limit=limit_per_hour,
            now=now
        )
        
        if not hour_allowed:
            raise HourLimitExceeded(
                message=f"Rate limit exceeded: {limit_per_hour} requests per hour",
                retry_after=hour_retry,
                limit_type="hour"
            )
        
        # Check day limit
        day_allowed, day_retry = await self._check_window(
            user_id=user_id,
            window_name="day",
            window_seconds=86400,
            limit=limit_per_day,
            now=now
        )
        
        if not day_allowed:
            raise DailyLimitExceeded(
                message=f"Rate limit exceeded: {limit_per_day} requests per day",
                retry_after=day_retry,
                limit_type="day"
            )
        
        return True, None, None
    
    async def _check_window(
        self,
        user_id: str,
        window_name: str,
        window_seconds: int,
        limit: int,
        now: datetime
    ) -> Tuple[bool, Optional[int]]:
        """
        Check rate limit for a specific time window using sliding window.
        
        Args:
            user_id: User identifier
            window_name: Name of the window (minute, hour, day)
            window_seconds: Window size in seconds
            limit: Maximum requests in window
            now: Current timestamp
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        key = f"rate_limit:{window_name}:{user_id}"
        
        # Current timestamp in milliseconds
        now_ms = int(now.timestamp() * 1000)
        
        # Window start timestamp
        window_start_ms = now_ms - (window_seconds * 1000)
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start_ms)
        
        # Count requests in current window
        pipe.zcard(key)
        
        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]
        
        # Check if limit exceeded
        if current_count >= limit:
            # Calculate retry after
            # Get oldest request in window
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp_ms = int(oldest[0][1])
                retry_after = int((oldest_timestamp_ms + (window_seconds * 1000) - now_ms) / 1000)
                retry_after = max(1, retry_after)  # At least 1 second
            else:
                retry_after = window_seconds
            
            return False, retry_after
        
        # Add current request to window
        await self.redis.zadd(key, {str(now_ms): now_ms})
        
        # Set expiration to window size + buffer
        await self.redis.expire(key, window_seconds + 60)
        
        return True, None
    
    async def get_usage_stats(
        self,
        user_id: str
    ) -> Dict[str, Dict[str, int]]:
        """
        Get current usage statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with usage stats for each window
        """
        now = datetime.utcnow()
        now_ms = int(now.timestamp() * 1000)
        
        stats = {}
        
        for window_name, window_seconds in [
            ("minute", 60),
            ("hour", 3600),
            ("day", 86400)
        ]:
            key = f"rate_limit:{window_name}:{user_id}"
            window_start_ms = now_ms - (window_seconds * 1000)
            
            # Count requests in window
            count = await self.redis.zcount(key, window_start_ms, now_ms)
            
            stats[window_name] = {
                "count": count,
                "window_seconds": window_seconds
            }
        
        return stats
    
    async def reset_user_limits(self, user_id: str):
        """
        Reset all rate limits for a user.
        
        Args:
            user_id: User identifier
        """
        for window_name in ["minute", "hour", "day"]:
            key = f"rate_limit:{window_name}:{user_id}"
            await self.redis.delete(key)
        
        logger.info(f"Reset rate limits for user {user_id}")
    
    async def increment_counter(
        self,
        user_id: str,
        counter_name: str,
        window_seconds: int = 86400
    ) -> int:
        """
        Increment a custom counter for a user.
        
        Useful for tracking specific actions beyond general rate limiting.
        
        Args:
            user_id: User identifier
            counter_name: Name of the counter
            window_seconds: Time window in seconds
            
        Returns:
            Current counter value
        """
        key = f"counter:{counter_name}:{user_id}"
        
        # Increment counter
        count = await self.redis.incr(key)
        
        # Set expiration on first increment
        if count == 1:
            await self.redis.expire(key, window_seconds)
        
        return count


class TierBasedRateLimiter(RateLimiter):
    """
    Rate limiter with tier-based limits.
    
    Different user tiers get different rate limits.
    """
    
    # Default limits per tier
    TIER_LIMITS = {
        "FREE": {
            "per_minute": 5,
            "per_hour": 50,
            "per_day": 100
        },
        "BASIC": {
            "per_minute": 10,
            "per_hour": 200,
            "per_day": 1000
        },
        "PREMIUM": {
            "per_minute": 30,
            "per_hour": 1000,
            "per_day": 10000
        },
        "ENTERPRISE": {
            "per_minute": 100,
            "per_hour": 10000,
            "per_day": 100000
        }
    }
    
    async def check_rate_limit_for_tier(
        self,
        user_id: str,
        tier: str
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check rate limit based on user tier.
        
        Args:
            user_id: User identifier
            tier: User tier (FREE, BASIC, PREMIUM, ENTERPRISE)
            
        Returns:
            Tuple of (is_allowed, limit_type, retry_after_seconds)
        """
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS["FREE"])
        
        return await self.check_rate_limit(
            user_id=user_id,
            limit_per_minute=limits["per_minute"],
            limit_per_hour=limits["per_hour"],
            limit_per_day=limits["per_day"]
        )
