"""
Cleanup Tasks
Async tasks for system cleanup and maintenance
"""

from typing import Dict, Any
from datetime import datetime, timedelta, timezone
import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="app.tasks.cleanup.cleanup_old_cache",
    bind=True
)
def cleanup_old_cache(self) -> Dict[str, Any]:
    """
    Cleanup old Redis cache entries.
    Runs periodically via Celery Beat.
    
    Returns:
        Cleanup statistics
    """
    try:
        import asyncio
        from app.core.dependencies import get_redis_client
        
        async def cleanup():
            redis = await get_redis_client()
            
            # Get all keys with TTL
            cursor = 0
            deleted = 0
            checked = 0
            
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match="cache:*",
                    count=100
                )
                
                for key in keys:
                    checked += 1
                    ttl = await redis.ttl(key)
                    
                    # Delete if expired or TTL is very old
                    if ttl < 0 or ttl > 86400 * 7:  # 7 days
                        await redis.delete(key)
                        deleted += 1
                
                if cursor == 0:
                    break
            
            return {"checked": checked, "deleted": deleted}
        
        result = asyncio.run(cleanup())
        
        logger.info(
            "Cache cleanup completed",
            task_id=self.request.id,
            **result
        )
        
        return {"status": "success", **result}
        
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.cleanup.cleanup_query_cache",
    bind=True
)
def cleanup_query_cache(self, days: int = 30) -> Dict[str, Any]:
    """
    Cleanup old query cache entries from database.
    Runs periodically via Celery Beat.
    
    Args:
        days: Delete cache entries older than this many days
        
    Returns:
        Cleanup statistics
    """
    try:
        import asyncio
        from app.db.session import get_session
        from app.models.user import QueryCache
        from sqlalchemy import delete
        
        async def cleanup():
            async with get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Delete old cache entries
                stmt = delete(QueryCache).where(
                    QueryCache.created_at < cutoff_date
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                return {"deleted": result.rowcount}
        
        result = asyncio.run(cleanup())
        
        logger.info(
            f"Query cache cleanup completed (older than {days} days)",
            task_id=self.request.id,
            **result
        )
        
        return {"status": "success", **result}
        
    except Exception as e:
        logger.error(f"Query cache cleanup failed: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.cleanup.cleanup_old_conversations",
    bind=True
)
def cleanup_old_conversations(self, days: int = 90) -> Dict[str, Any]:
    """
    Archive or delete very old conversations.
    
    Args:
        days: Archive conversations older than this many days
        
    Returns:
        Cleanup statistics
    """
    try:
        import asyncio
        from app.db.session import get_session
        from app.models.user import Conversation
        from sqlalchemy import select, update
        
        async def cleanup():
            async with get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Mark old conversations as archived
                stmt = (
                    update(Conversation)
                    .where(Conversation.last_message_at < cutoff_date)
                    .where(Conversation.is_archived == False)
                    .values(is_archived=True, archived_at=datetime.now(timezone.utc))
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                return {"archived": result.rowcount}
        
        result = asyncio.run(cleanup())
        
        logger.info(
            f"Conversations cleanup completed (older than {days} days)",
            task_id=self.request.id,
            **result
        )
        
        return {"status": "success", **result}
        
    except Exception as e:
        logger.error(f"Conversations cleanup failed: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.cleanup.cleanup_failed_tasks",
    bind=True
)
def cleanup_failed_tasks(self) -> Dict[str, Any]:
    """
    Cleanup failed Celery task results from Redis.
    
    Returns:
        Cleanup statistics
    """
    try:
        import asyncio
        from app.core.dependencies import get_redis_client
        
        async def cleanup():
            redis = await get_redis_client()
            
            # Get all celery result keys
            cursor = 0
            deleted = 0
            
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match="celery-task-meta-*",
                    count=100
                )
                
                for key in keys:
                    # Get task result
                    result = await redis.get(key)
                    if result and b'"status": "FAILURE"' in result:
                        # Delete failed task results older than 1 day
                        ttl = await redis.ttl(key)
                        if ttl < 86400:  # Less than 1 day remaining
                            await redis.delete(key)
                            deleted += 1
                
                if cursor == 0:
                    break
            
            return {"deleted": deleted}
        
        result = asyncio.run(cleanup())
        
        logger.info(
            "Failed tasks cleanup completed",
            task_id=self.request.id,
            **result
        )
        
        return {"status": "success", **result}
        
    except Exception as e:
        logger.error(f"Failed tasks cleanup failed: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.cleanup.cleanup_expired_temp_files",
    bind=True
)
def cleanup_expired_temp_files(self) -> Dict[str, Any]:
    """
    Cleanup expired temporary files from MinIO/S3 storage.
    Runs periodically via Celery Beat.
    
    Returns:
        Cleanup statistics with deleted file count
    """
    try:
        import asyncio
        from app.services.storage_service import get_storage_service
        
        logger.info("Starting cleanup of expired temporary files", task_id=self.request.id)
        
        storage_service = get_storage_service()
        
        deleted_count = asyncio.run(storage_service.cleanup_expired_files())
        
        logger.info(
            "Temp files cleanup completed",
            task_id=self.request.id,
            deleted_count=deleted_count
        )
        
        return {
            "status": "success",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Temp files cleanup failed: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}
