"""
User Management API Endpoints
Endpoints for user profile and conversation management
"""

from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from pydantic import BaseModel, Field
import structlog

from app.db.session import get_db
from app.models.user import UserProfile, Conversation, Message
from app.core.security import get_current_user_id

logger = structlog.get_logger()
router = APIRouter()


# Response Models
class UserProfileResponse(BaseModel):
    """User profile response model."""
    id: str
    external_user_id: str
    username: str
    email: Optional[str]
    full_name: Optional[str]
    total_query_count: int
    total_tokens_used: int
    language: str
    timezone: str
    last_active_at: Optional[datetime]
    created_at: datetime


class ConversationResponse(BaseModel):
    """Conversation response model."""
    id: str
    title: Optional[str]
    summary: Optional[str]
    message_count: int
    total_tokens: int
    last_message_at: Optional[datetime]
    created_at: datetime


class MessageResponse(BaseModel):
    """Message response model."""
    id: str
    role: str
    content: str
    tokens: int
    sources: Optional[List[str]]
    feedback_rating: Optional[int]
    created_at: datetime


# Get user profile
@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Get current user's profile."""
    # Get user by external_user_id
    stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return UserProfileResponse(
        id=str(user.id),
        external_user_id=user.external_user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        total_query_count=user.total_query_count,
        total_tokens_used=user.total_tokens_used,
        language=user.language,
        timezone=user.timezone,
        last_active_at=user.last_active_at,
        created_at=user.created_at
    )


# Update user profile
@router.patch("/profile")
async def update_user_profile(
    language: Optional[str] = None,
    timezone: Optional[str] = None,
    preferences: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Update user profile settings."""
    # Get user by external_user_id
    stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    if language:
        user.language = language
    if timezone:
        user.timezone = timezone
    if preferences:
        user.preferences.update(preferences)
    
    await db.commit()
    
    return {"status": "success", "message": "Profile updated"}


# Get user conversations
@router.get("/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Get user's conversations."""
    # Get user by external_user_id
    stmt_user = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result_user = await db.execute(stmt_user)
    user = result_user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Query conversations
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.last_message_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    
    return [
        ConversationResponse(
            id=str(conv.id),
            title=conv.title,
            summary=conv.summary,
            message_count=conv.message_count,
            total_tokens=conv.total_tokens,
            last_message_at=conv.last_message_at,
            created_at=conv.created_at
        )
        for conv in conversations
    ]


# Get conversation messages
@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Get messages in a conversation."""
    # Verify conversation ownership - Get user by external_user_id
    stmt_user = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result_user = await db.execute(stmt_user)
    user = result_user.scalar_one_or_none()
    conversation = await db.get(Conversation, conversation_id)
    
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Query messages
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    return [
        MessageResponse(
            id=str(msg.id),
            role=msg.role.value,
            content=msg.content,
            tokens=msg.tokens,
            sources=msg.sources,
            feedback_rating=msg.feedback_rating,
            created_at=msg.created_at
        )
        for msg in reversed(messages)  # Return in chronological order
    ]


# Delete conversation
@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a conversation and all its messages.
    
    Returns:
        - 200: Conversation deleted successfully
        - 404: Conversation not found or doesn't belong to user
        - 500: Database error during deletion
    """
    try:
        # Verify conversation ownership - Get user by external_user_id
        stmt_user = select(UserProfile).where(UserProfile.external_user_id == user_id)
        result_user = await db.execute(stmt_user)
        user = result_user.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        conversation = await db.get(Conversation, conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        if conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"  # Don't reveal it exists
            )
        
        # Delete conversation (cascade will delete messages)
        await db.delete(conversation)
        await db.commit()
        
        return {
            "status": "success",
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error and rollback
        await db.rollback()
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )


# Get user statistics
@router.get("/statistics")
async def get_user_statistics(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Get user usage statistics."""
    # Get user by external_user_id
    stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Calculate statistics
    conversation_count = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user.id)
    )
    
    return {
        "total_queries": user.total_query_count,
        "total_tokens": user.total_tokens_used,
        "total_input_tokens": user.total_input_tokens,
        "total_output_tokens": user.total_output_tokens,
        "total_conversations": conversation_count,
        "total_feedback": user.total_feedback_given,
        "created_at": user.created_at,
        "last_active": user.last_active_at
    }


# Clear user history
@router.post("/clear-history")
async def clear_user_history(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Clear all user conversations and messages."""
    # Get user by external_user_id
    stmt_user = select(UserProfile).where(UserProfile.external_user_id == user_id)
    result_user = await db.execute(stmt_user)
    user = result_user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete all conversations (cascade will delete messages)
    stmt = select(Conversation).where(Conversation.user_id == user.id)
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    
    for conv in conversations:
        await db.delete(conv)
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Cleared {len(conversations)} conversations"
    }
