"""
User Tasks
Async tasks for user statistics (analytics only)

NOTE: Subscription and limit management is handled by Users system.
RAG Core only tracks usage statistics for analytics purposes.
"""

from typing import Dict, Any
from datetime import datetime, timedelta, timezone
import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


# NOTE: reset_user_daily_limit and reset_all_daily_limits tasks removed
# Subscription limits are now managed by Users system


@celery_app.task(
    name="app.tasks.user.update_user_statistics",
    bind=True
)
def update_user_statistics(self, user_id: str) -> Dict[str, Any]:
    """
    Update user statistics and analytics.
    
    Args:
        user_id: User ID
        
    Returns:
        Update result
    """
    try:
        import asyncio
        from app.db.session import get_session
        from app.models.user import UserProfile, Conversation, Message
        from sqlalchemy import select, func
        
        async def update_stats():
            async with get_session() as session:
                user = await session.get(UserProfile, user_id)
                if not user:
                    return {"status": "not_found"}
                
                # Calculate statistics
                total_conversations = await session.scalar(
                    select(func.count()).select_from(Conversation).where(
                        Conversation.user_id == user.id
                    )
                )
                
                total_messages = await session.scalar(
                    select(func.count()).select_from(Message).join(
                        Conversation
                    ).where(
                        Conversation.user_id == user.id
                    )
                )
                
                total_tokens = await session.scalar(
                    select(func.sum(Message.tokens)).select_from(Message).join(
                        Conversation
                    ).where(
                        Conversation.user_id == user.id
                    )
                )
                
                # Update user profile
                user.total_tokens_used = total_tokens or 0
                user.last_active_at = datetime.now(timezone.utc)
                
                await session.commit()
                
                return {
                    "status": "success",
                    "user_id": user_id,
                    "total_conversations": total_conversations or 0,
                    "total_messages": total_messages or 0,
                    "total_tokens": total_tokens or 0
                }
        
        result = asyncio.run(update_stats())
        
        logger.info(
            "User statistics updated",
            task_id=self.request.id,
            user_id=user_id
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Failed to update user statistics: {e}",
            task_id=self.request.id,
            user_id=user_id
        )
        return {"status": "error", "error": str(e)}


# NOTE: calculate_user_tier task removed.
# Subscription/tier management is handled entirely by the Users system.
# See: Users system /srv/backend/subscriptions/models.py
