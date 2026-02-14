"""
Notification Tasks
Async tasks for sending notifications and updates
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import httpx
import structlog

from app.celery_app import celery_app
from app.config.settings import settings

logger = structlog.get_logger()


@celery_app.task(
    name="app.tasks.notifications.send_query_result_to_users",
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def send_query_result_to_users(
    self,
    user_id: str,
    conversation_id: str,
    message_id: str,
    query: str,
    answer: str,
    sources: List[str],
    tokens_used: int,
    processing_time_ms: int
) -> Dict[str, Any]:
    """
    Send query result to Users system for notification/webhook.
    
    Args:
        user_id: User ID
        conversation_id: Conversation ID
        message_id: Message ID
        query: User query
        answer: System answer
        sources: Source documents
        tokens_used: Tokens consumed
        processing_time_ms: Processing time
        
    Returns:
        Notification result
    """
    try:
        if not settings.users_api_url or not settings.users_api_key:
            logger.warning("Users API not configured, skipping notification")
            return {"status": "skipped", "reason": "not_configured"}
        
        # Prepare payload
        payload = {
            "event_type": "query_completed",
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "data": {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "query": query,
                "answer": answer,
                "sources": sources,
                "tokens_used": tokens_used,
                "processing_time_ms": processing_time_ms,
            }
        }
        
        # Send to Users API
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{settings.users_api_url}/notifications/webhook",
                json=payload,
                headers={
                    "X-API-Key": settings.users_api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        
        logger.info(
            "Query result sent to Users system",
            task_id=self.request.id,
            user_id=user_id,
            message_id=message_id
        )
        
        return {
            "status": "success",
            "user_id": user_id,
            "message_id": message_id
        }
        
    except httpx.HTTPError as e:
        logger.error(
            f"Failed to send notification: {e}",
            task_id=self.request.id,
            user_id=user_id
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 30)
    
    except Exception as e:
        logger.error(
            f"Notification task failed: {e}",
            task_id=self.request.id,
            user_id=user_id
        )
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.notifications.send_usage_statistics",
    bind=True
)
def send_usage_statistics(self) -> Dict[str, Any]:
    """
    Send hourly usage statistics to Users system.
    Runs periodically via Celery Beat.
    
    Returns:
        Send result
    """
    try:
        import asyncio
        from app.db.session import get_session
        from sqlalchemy import select, func
        from app.models.user import UserProfile, Message
        
        if not settings.users_api_url or not settings.users_api_key:
            return {"status": "skipped", "reason": "not_configured"}
        
        # Get statistics from database
        async def get_stats():
            async with get_session() as session:
                # Get hourly stats
                one_hour_ago = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
                
                total_queries = await session.scalar(
                    select(func.count()).select_from(Message).where(
                        Message.created_at >= one_hour_ago
                    )
                )
                
                total_tokens = await session.scalar(
                    select(func.sum(Message.tokens)).select_from(Message).where(
                        Message.created_at >= one_hour_ago
                    )
                )
                
                active_users = await session.scalar(
                    select(func.count(func.distinct(UserProfile.id))).select_from(UserProfile).where(
                        UserProfile.last_active_at >= one_hour_ago
                    )
                )
                
                return {
                    "total_queries": total_queries or 0,
                    "total_tokens": total_tokens or 0,
                    "active_users": active_users or 0,
                    "period_start": one_hour_ago.isoformat() + "Z",
                    "period_end": datetime.now(timezone.utc).isoformat() + "Z"
                }
        
        stats = asyncio.run(get_stats())
        
        # Send to Users API
        payload = {
            "event_type": "usage_statistics",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "data": stats
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{settings.users_api_url}/statistics/core",
                json=payload,
                headers={
                    "X-API-Key": settings.users_api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        
        logger.info(
            "Usage statistics sent",
            task_id=self.request.id,
            **stats
        )
        
        return {"status": "success", "stats": stats}
        
    except Exception as e:
        logger.error(f"Failed to send statistics: {e}", task_id=self.request.id)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.notifications.send_system_notification",
    bind=True,
    max_retries=3
)
def send_system_notification(
    self,
    notification_type: str,
    title: str,
    message: str,
    user_ids: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send system notification to users.
    
    Args:
        notification_type: Type of notification (info, warning, error)
        title: Notification title
        message: Notification message
        user_ids: List of user IDs (None = all users)
        metadata: Additional metadata
        
    Returns:
        Send result
    """
    try:
        if not settings.users_api_url or not settings.users_api_key:
            return {"status": "skipped", "reason": "not_configured"}
        
        payload = {
            "event_type": "system_notification",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "data": {
                "type": notification_type,
                "title": title,
                "message": message,
                "user_ids": user_ids,
                "metadata": metadata or {}
            }
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{settings.users_api_url}/notifications/system",
                json=payload,
                headers={
                    "X-API-Key": settings.users_api_key,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
        
        logger.info(
            "System notification sent",
            task_id=self.request.id,
            type=notification_type,
            user_count=len(user_ids) if user_ids else "all"
        )
        
        return {"status": "success", "notification_type": notification_type}
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}", task_id=self.request.id)
        raise self.retry(exc=e, countdown=60)
