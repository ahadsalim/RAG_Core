"""
User Tasks
Async tasks for user statistics (analytics only)

NOTE: Subscription and limit management is handled by Users system.
RAG Core only tracks usage statistics for analytics purposes.
"""

from typing import Dict, Any
from datetime import datetime, timedelta
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
                user.total_conversations = total_conversations or 0
                user.total_tokens_used = total_tokens or 0
                user.last_stats_update = datetime.utcnow()
                
                await session.commit()
                
                return {
                    "status": "success",
                    "user_id": user_id,
                    "total_conversations": total_conversations or 0,
                    "total_messages": total_messages or 0,
                    "total_tokens": total_tokens or 0
                }
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(update_stats())
        
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


@celery_app.task(
    name="app.tasks.user.calculate_user_tier",
    bind=True
)
def calculate_user_tier(self, user_id: str) -> Dict[str, Any]:
    """
    Calculate and update user tier based on usage.
    
    Args:
        user_id: User ID
        
    Returns:
        Tier calculation result
    """
    try:
        import asyncio
        from app.db.session import get_session
        from app.models.user import UserProfile, UserTier
        
        async def calculate():
            async with get_session() as session:
                user = await session.get(UserProfile, user_id)
                if not user:
                    return {"status": "not_found"}
                
                # Calculate tier based on usage
                old_tier = user.tier
                
                if user.total_query_count > 10000:
                    new_tier = UserTier.ENTERPRISE
                elif user.total_query_count > 1000:
                    new_tier = UserTier.PREMIUM
                elif user.total_query_count > 100:
                    new_tier = UserTier.BASIC
                else:
                    new_tier = UserTier.FREE
                
                if new_tier != old_tier:
                    user.tier = new_tier
                    user.tier_updated_at = datetime.utcnow()
                    await session.commit()
                    
                    return {
                        "status": "updated",
                        "user_id": user_id,
                        "old_tier": old_tier.value,
                        "new_tier": new_tier.value
                    }
                else:
                    return {
                        "status": "unchanged",
                        "user_id": user_id,
                        "tier": old_tier.value
                    }
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(calculate())
        
        if result.get("status") == "updated":
            logger.info(
                "User tier updated",
                task_id=self.request.id,
                **result
            )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Failed to calculate user tier: {e}",
            task_id=self.request.id,
            user_id=user_id
        )
        return {"status": "error", "error": str(e)}
