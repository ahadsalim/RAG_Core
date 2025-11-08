"""
Query Processing API Endpoints
Main endpoints for RAG query processing
"""

from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from pydantic import BaseModel, Field, validator
import structlog

from app.db.session import get_db
from app.rag.pipeline import RAGPipeline, RAGQuery
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.core.dependencies import get_redis_client
from app.core.rate_limiter import TierBasedRateLimiter
from app.core.exceptions import (
    to_http_exception,
    RateLimitException,
    RecordNotFoundException,
    AuthorizationException,
    ValidationException
)
from app.core.metrics import (
    record_query_metrics,
    record_rate_limit_violation,
    query_duration
)
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
    1. Validates user permissions and rate limits
    2. Processes the query through RAG
    3. Saves conversation history (with transaction)
    4. Returns the response
    5. Records metrics
    """
    start_time = datetime.utcnow()
    
    try:
        # Get user profile with eager loading to avoid N+1 queries
        stmt = select(UserProfile).options(
            selectinload(UserProfile.conversations)
        ).where(UserProfile.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            # Create user profile if doesn't exist
            user = UserProfile(
                id=user_id,
                external_user_id=user_id,
                username=f"user_{user_id[:8]}",
                created_at=datetime.utcnow()
            )
            db.add(user)
            await db.flush()  # Flush to get ID without committing
        
        # Check rate limits (sliding window)
        redis = await get_redis_client()
        rate_limiter = TierBasedRateLimiter(redis)
        
        try:
            await rate_limiter.check_rate_limit_for_tier(
                user_id=str(user.id),
                tier=user.tier.value
            )
        except RateLimitException as e:
            # Record rate limit violation
            record_rate_limit_violation(
                limit_type=e.limit_type if hasattr(e, 'limit_type') else 'unknown',
                user_tier=user.tier.value
            )
            raise to_http_exception(e)
        
        # Check daily query limit (database-based)
        if not user.can_make_query():
            record_rate_limit_violation(
                limit_type='daily',
                user_tier=user.tier.value
            )
            raise RateLimitException(
                message="Daily query limit exceeded",
                retry_after=86400,
                limit_type='daily'
            )
        
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = await db.get(Conversation, request.conversation_id)
            if conversation and conversation.user_id != user.id:
                raise AuthorizationException(
                    "Access denied to this conversation"
                )
        
        if not conversation:
            conversation = Conversation(
                id=uuid.uuid4(),
                user_id=user.id,
                title=request.query[:100],
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
        
        # Use transaction for database operations
        async with db.begin_nested():  # Savepoint for rollback
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
        
        # Commit all changes
        await db.commit()
        
        # Record metrics
        duration = (datetime.utcnow() - start_time).total_seconds()
        record_query_metrics(
            status='success',
            user_tier=user.tier.value,
            language=request.language,
            duration=duration,
            tokens=rag_response.total_tokens,
            model=rag_response.model_used
        )
        
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
        
    except (RateLimitException, AuthorizationException, ValidationException) as e:
        # Convert custom exceptions to HTTP exceptions
        raise to_http_exception(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", user_id=user_id, exc_info=True)
        
        # Record error metrics
        duration = (datetime.utcnow() - start_time).total_seconds()
        record_query_metrics(
            status='error',
            user_tier='unknown',
            language=request.language,
            duration=duration,
            tokens=0,
            model='unknown'
        )
        
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
        """Generate streaming tokens with real LLM streaming."""
        try:
            # Get user profile
            user = await db.get(UserProfile, user_id)
            if not user or not user.can_make_query():
                yield json.dumps({"error": "Unauthorized or limit exceeded"}) + "\n"
                return
            
            # Check rate limits
            redis = await get_redis_client()
            rate_limiter = TierBasedRateLimiter(redis)
            
            try:
                await rate_limiter.check_rate_limit_for_tier(
                    user_id=str(user.id),
                    tier=user.tier.value
                )
            except RateLimitException:
                yield json.dumps({"error": "Rate limit exceeded"}) + "\n"
                return
            
            # Get or create conversation
            conversation = None
            if request.conversation_id:
                conversation = await db.get(Conversation, request.conversation_id)
            
            if not conversation:
                conversation = Conversation(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=request.query[:100],
                    created_at=datetime.utcnow()
                )
                db.add(conversation)
                await db.flush()
            
            # Send metadata first
            yield json.dumps({
                "type": "metadata",
                "conversation_id": str(conversation.id),
                "timestamp": datetime.utcnow().isoformat()
            }) + "\n"
            
            # Process RAG pipeline for context retrieval
            pipeline = RAGPipeline()
            
            # Get embeddings and retrieve chunks (non-streaming part)
            from app.rag.pipeline import RAGQuery as InternalRAGQuery
            rag_query = InternalRAGQuery(
                text=request.query,
                user_id=str(user.id),
                conversation_id=str(conversation.id),
                language=request.language,
                max_chunks=request.max_results,
                filters=request.filters,
                use_cache=False,  # Don't use cache for streaming
                use_reranking=request.use_reranking
            )
            
            # Get chunks (this part is not streamed)
            enhanced_query = await pipeline._enhance_query(rag_query)
            query_embedding = await pipeline._generate_embedding(enhanced_query)
            chunks = await pipeline._retrieve_chunks(
                query_embedding,
                enhanced_query,
                rag_query.filters,
                limit=rag_query.max_chunks * 3
            )
            
            if rag_query.use_reranking and len(chunks) > rag_query.max_chunks:
                chunks = await pipeline._rerank_chunks(
                    enhanced_query,
                    chunks,
                    top_k=rag_query.max_chunks
                )
            else:
                chunks = chunks[:rag_query.max_chunks]
            
            # Send sources
            sources = pipeline._extract_sources(chunks)
            yield json.dumps({
                "type": "sources",
                "sources": sources
            }) + "\n"
            
            # Stream LLM response
            full_answer = ""
            async for token in pipeline._generate_answer_stream(
                request.query,
                chunks,
                request.language,
                str(conversation.id)
            ):
                full_answer += token
                yield json.dumps({
                    "type": "token",
                    "content": token
                }) + "\n"
            
            # Send finish signal
            yield json.dumps({
                "type": "finish",
                "finish_reason": "stop"
            }) + "\n"
            
            # Save messages to database (background)
            user_message = DBMessage(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=request.query,
                created_at=datetime.utcnow()
            )
            db.add(user_message)
            
            assistant_message = DBMessage(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=full_answer,
                sources=sources,
                created_at=datetime.utcnow()
            )
            db.add(assistant_message)
            
            conversation.message_count += 2
            user.increment_query_count()
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"
    
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
