"""
Query Processing API Endpoints
Main endpoints for RAG query processing
"""

from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
import structlog

from app.db.session import get_db
from app.rag.pipeline import RAGPipeline, RAGQuery
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.core.dependencies import get_redis_client
from app.config.settings import settings

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class QueryRequest(BaseModel):
    """Query request model."""
    query: str = Field(..., min_length=1, max_length=settings.max_query_length)
    conversation_id: Optional[str] = None
    language: str = Field(default="fa", pattern="^(fa|en|ar)$")
    max_results: int = Field(default=5, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = None
    use_cache: bool = Field(default=True)
    use_reranking: bool = Field(default=True)
    stream: bool = Field(default=False)
    
    @validator("query")
    def clean_query(cls, v):
        """Clean and validate query text."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Query too short")
        return v


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    sources: list[str]
    conversation_id: str
    message_id: str
    tokens_used: int
    processing_time_ms: int
    cached: bool = False


class FeedbackRequest(BaseModel):
    """Feedback request model."""
    message_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback_type: str = Field(default="general")
    feedback_text: Optional[str] = None
    suggested_response: Optional[str] = None


class StreamToken(BaseModel):
    """Streaming token response."""
    token: str
    finish_reason: Optional[str] = None


# Main query endpoint
@router.post("/", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> QueryResponse:
    """
    Process a user query through the RAG pipeline.
    
    This endpoint:
    1. Validates user permissions
    2. Processes the query through RAG
    3. Saves conversation history
    4. Returns the response
    """
    try:
        # Get user profile
        user = await db.get(UserProfile, user_id)
        if not user:
            # Create user profile if doesn't exist
            user = UserProfile(
                id=user_id,
                external_user_id=user_id,
                username=f"user_{user_id[:8]}",
                created_at=datetime.utcnow()
            )
            db.add(user)
            await db.commit()
        
        # Check user limits
        if not user.can_make_query():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily query limit exceeded"
            )
        
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = await db.get(Conversation, request.conversation_id)
            if conversation and conversation.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this conversation"
                )
        
        if not conversation:
            conversation = Conversation(
                id=uuid.uuid4(),
                user_id=user.id,
                title=request.query[:100],  # Use first 100 chars as title
                created_at=datetime.utcnow()
            )
            db.add(conversation)
        
        # Create RAG query
        rag_query = RAGQuery(
            text=request.query,
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            language=request.language,
            max_chunks=request.max_results,
            filters=request.filters,
            use_cache=request.use_cache,
            use_reranking=request.use_reranking
        )
        
        # Process through RAG pipeline
        pipeline = RAGPipeline()
        rag_response = await pipeline.process(rag_query)
        
        # Save user message
        user_message = DBMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=request.query,
            created_at=datetime.utcnow()
        )
        db.add(user_message)
        
        # Save assistant message
        assistant_message = DBMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=rag_response.answer,
            tokens=rag_response.total_tokens,
            processing_time_ms=rag_response.processing_time_ms,
            retrieved_chunks=[
                {
                    "text": chunk.text,
                    "score": chunk.score,
                    "source": chunk.source,
                    "metadata": chunk.metadata
                }
                for chunk in rag_response.chunks
            ],
            sources=rag_response.sources,
            model_used=rag_response.model_used,
            created_at=datetime.utcnow()
        )
        db.add(assistant_message)
        
        # Update conversation
        conversation.message_count += 2
        conversation.total_tokens += rag_response.total_tokens
        conversation.last_message_at = datetime.utcnow()
        
        # Update user statistics
        user.increment_query_count()
        user.total_tokens_used += rag_response.total_tokens
        
        # Commit changes
        await db.commit()
        
        # Background task: Update user daily limit reset
        background_tasks.add_task(reset_user_daily_limit_if_needed, user.id)
        
        # Return response
        return QueryResponse(
            answer=rag_response.answer,
            sources=rag_response.sources,
            conversation_id=str(conversation.id),
            message_id=str(assistant_message.id),
            tokens_used=rag_response.total_tokens,
            processing_time_ms=rag_response.processing_time_ms,
            cached=rag_response.cached
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed"
        )


# Streaming query endpoint
@router.post("/stream")
async def process_query_stream(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Process a query with streaming response.
    
    Returns a stream of tokens as they are generated.
    """
    if not settings.enable_streaming:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Streaming is not enabled"
        )
    
    async def generate():
        """Generate streaming tokens."""
        try:
            # Similar setup as non-streaming endpoint
            user = await db.get(UserProfile, user_id)
            if not user or not user.can_make_query():
                yield '{"error": "Unauthorized or limit exceeded"}'
                return
            
            # Process query with streaming
            # TODO: Implement streaming RAG pipeline
            pipeline = RAGPipeline()
            
            # For now, return chunked response
            rag_query = RAGQuery(
                text=request.query,
                user_id=str(user.id),
                language=request.language,
                max_chunks=request.max_results
            )
            
            response = await pipeline.process(rag_query)
            
            # Simulate streaming by chunking the response
            import json
            words = response.answer.split()
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i:i+3])
                token_data = StreamToken(token=chunk)
                yield json.dumps(token_data.dict(), ensure_ascii=False) + "\n"
                await asyncio.sleep(0.05)  # Simulate processing delay
            
            # Send finish token
            finish_token = StreamToken(token="", finish_reason="stop")
            yield json.dumps(finish_token.dict(), ensure_ascii=False) + "\n"
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f'{{"error": "{str(e)}"}}'
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )


# Feedback endpoint
@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Submit feedback for a message.
    
    This helps improve the system's responses.
    """
    try:
        # Get the message
        message = await db.get(DBMessage, request.message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Verify user owns the conversation
        conversation = await db.get(Conversation, message.conversation_id)
        user = await db.get(UserProfile, user_id)
        
        if not conversation or conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update message feedback
        message.feedback_rating = request.rating
        message.feedback_text = request.feedback_text
        
        # Update user statistics
        user.total_feedback_given += 1
        
        # Create feedback record for analysis
        from app.models.user import UserFeedback
        feedback = UserFeedback(
            id=uuid.uuid4(),
            user_id=user.id,
            message_id=message.id,
            rating=request.rating,
            feedback_type=request.feedback_type,
            feedback_text=request.feedback_text,
            suggested_response=request.suggested_response,
            created_at=datetime.utcnow()
        )
        db.add(feedback)
        
        await db.commit()
        
        return {"status": "success", "message": "Feedback received"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


# Helper functions
async def reset_user_daily_limit_if_needed(user_id: str):
    """Reset user's daily query count if needed."""
    try:
        redis = await get_redis_client()
        
        # Check if we need to reset (once per day)
        reset_key = f"user:daily_reset:{user_id}:{datetime.utcnow().date()}"
        already_reset = await redis.get(reset_key)
        
        if not already_reset:
            # Reset in database
            from app.db.session import get_session
            async with get_session() as db:
                user = await db.get(UserProfile, user_id)
                if user:
                    user.daily_query_count = 0
                    await db.commit()
            
            # Mark as reset for today
            await redis.setex(reset_key, 86400, "1")  # Expire after 24 hours
            
    except Exception as e:
        logger.error(f"Failed to reset user daily limit: {e}")
