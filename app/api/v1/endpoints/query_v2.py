"""
Query Processing API Endpoints - Version 2
Enhanced version with MinIO link support from Users system
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, validator, HttpUrl
import structlog
import json

from app.db.session import get_db
from app.rag.pipeline import RAGPipeline, RAGQuery
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.config.settings import settings
from app.services.file_processing_service import get_file_processing_service
from app.services.storage_service import get_storage_service

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class FileAttachment(BaseModel):
    """File attachment model with MinIO link."""
    filename: str = Field(..., description="Original filename")
    minio_url: str = Field(..., description="MinIO object URL or key")
    file_type: str = Field(..., description="MIME type")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    
    @validator("filename")
    def validate_filename(cls, v):
        """Validate filename."""
        if not v or len(v) < 1:
            raise ValueError("Filename cannot be empty")
        return v


class QueryRequestV2(BaseModel):
    """Enhanced query request model with file links."""
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=settings.max_query_length,
        description="User's question in natural language"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Optional conversation ID to continue existing conversation"
    )
    language: str = Field(
        default="fa", 
        pattern="^(fa|en|ar)$",
        description="Query language"
    )
    max_results: int = Field(
        default=5, 
        ge=1, 
        le=20,
        description="Maximum number of source documents to retrieve"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional filters for document search"
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results if available"
    )
    use_reranking: bool = Field(
        default=True,
        description="Whether to rerank search results"
    )
    user_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional user preferences"
    )
    file_attachments: Optional[List[FileAttachment]] = Field(
        None,
        max_items=5,
        description="List of file attachments (MinIO links from Users system)"
    )
    
    @validator("query")
    def clean_query(cls, v):
        """Clean and validate query text."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Query too short")
        return v
    
    @validator("file_attachments")
    def validate_files(cls, v):
        """Validate file attachments."""
        if v and len(v) > 5:
            raise ValueError("Maximum 5 files allowed")
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
    files_processed: Optional[int] = Field(None, description="Number of files processed")


# Enhanced query endpoint with MinIO link support
@router.post(
    "/v2", 
    response_model=QueryResponse,
    summary="Process User Query with MinIO File Links",
    description="""
    Process a user's question through the RAG pipeline.
    Accepts file links (MinIO URLs) from Users system instead of direct file uploads.
    
    **Workflow:**
    1. Users system uploads files to MinIO
    2. Users system sends query + MinIO links to RAG Core
    3. RAG Core downloads files from MinIO
    4. RAG Core processes files and generates answer
    
    **Benefits:**
    - Single file upload (to Users system only)
    - Reduced network traffic
    - Centralized file management
    - Better security and access control
    """
)
async def process_query_v2(
    request: QueryRequestV2,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> QueryResponse:
    """Process a user query with file links from Users system."""
    try:
        # Get user profile
        stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            # Create user profile if doesn't exist
            user = UserProfile(
                id=uuid.uuid4(),
                external_user_id=user_id,
                username=f"user_{user_id[:8] if len(user_id) >= 8 else user_id}",
                created_at=datetime.utcnow()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        # Check user limits
        if not user.can_make_query():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily query limit exceeded"
            )
        
        # Process file attachments if any
        file_context = ""
        processed_files_count = 0
        
        if request.file_attachments:
            logger.info(
                f"Processing {len(request.file_attachments)} file links from MinIO",
                user_id=user_id
            )
            
            # Get services
            file_processor = get_file_processing_service()
            storage_service = get_storage_service()
            
            # Download and process files from MinIO
            file_data = []
            for attachment in request.file_attachments:
                try:
                    # Download file from MinIO using the provided URL/key
                    file_content = await storage_service.download_temp_file(
                        attachment.minio_url
                    )
                    
                    file_data.append({
                        'content': file_content,
                        'filename': attachment.filename,
                        'file_type': attachment.file_type
                    })
                    
                except Exception as e:
                    logger.error(
                        f"Failed to download file from MinIO: {e}",
                        minio_url=attachment.minio_url,
                        filename=attachment.filename
                    )
                    # Continue with other files
                    continue
            
            if file_data:
                # Process files (extract text)
                processing_results = await file_processor.process_multiple_files(file_data)
                
                # Combine extracted text
                file_context = file_processor.combine_extracted_texts(processing_results)
                processed_files_count = len([r for r in processing_results if r.get('text')])
                
                logger.info(
                    "Files processed successfully",
                    user_id=user_id,
                    file_count=processed_files_count,
                    total_text_length=len(file_context)
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
                title=request.query[:100],
                message_count=0,
                total_tokens=0,
                created_at=datetime.utcnow()
            )
            db.add(conversation)
            await db.flush()
        
        # Combine query with file context
        enhanced_query = request.query
        if file_context:
            enhanced_query = f"{request.query}\n\n[محتوای فایل‌های ضمیمه:]\n{file_context}"
        
        # Create RAG query
        rag_query = RAGQuery(
            text=enhanced_query,
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            language=request.language,
            max_chunks=request.max_results,
            filters=request.filters,
            use_cache=request.use_cache,
            use_reranking=request.use_reranking,
            user_preferences=request.user_preferences
        )
        
        # Process through RAG pipeline
        pipeline = RAGPipeline()
        rag_response = await pipeline.process(rag_query)
        
        # Save user message
        user_message_content = request.query
        if request.file_attachments:
            file_info = "\n\n[فایل‌های ضمیمه: " + ", ".join(
                [f"{f.filename}" for f in request.file_attachments]
            ) + "]"
            user_message_content += file_info
        
        user_message = DBMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message_content,
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
        
        # Background task: Send result to Users system
        from app.tasks.notifications import send_query_result_to_users
        send_query_result_to_users.delay(
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            message_id=str(assistant_message.id),
            query=request.query,
            answer=rag_response.answer,
            sources=rag_response.sources,
            tokens_used=rag_response.total_tokens,
            processing_time_ms=rag_response.processing_time_ms,
            has_attachments=bool(request.file_attachments),
            file_count=len(request.file_attachments) if request.file_attachments else 0
        )
        
        # Return response
        return QueryResponse(
            answer=rag_response.answer,
            sources=rag_response.sources,
            conversation_id=str(conversation.id),
            message_id=str(assistant_message.id),
            tokens_used=rag_response.total_tokens,
            processing_time_ms=rag_response.processing_time_ms,
            cached=rag_response.cached,
            files_processed=processed_files_count if request.file_attachments else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query processing failed"
        )
