"""
Streaming Query Processing API Endpoint
پردازش سوال با پاسخ استریم (Server-Sent Events)
"""

from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import pytz
import jdatetime

from app.db.session import get_db
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.config.settings import settings
from app.services.file_analysis_service import get_file_analysis_service
from app.services.conversation_memory import get_conversation_memory
from app.llm.openai_provider import OpenAIProvider
from app.llm.base import LLMConfig, LLMProvider as LLMProviderEnum, Message

# Import models from main query endpoint
from app.api.v1.endpoints.query import QueryRequest, FileAttachment

logger = structlog.get_logger()
router = APIRouter()


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: Optional[str]
) -> Conversation:
    """Get existing or create new conversation."""
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user_id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            return conversation
    
    # Create new conversation
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title="گفتگوی جدید",
        message_count=0,
        total_tokens=0,
        created_at=datetime.utcnow()
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def analyze_files_for_query(
    file_attachments: List[FileAttachment],
    query: str
) -> Optional[str]:
    """Analyze attached files using LLM."""
    if not file_attachments:
        return None
    
    file_analysis_service = get_file_analysis_service()
    analyses = []
    
    for file in file_attachments:
        try:
            analysis = await file_analysis_service.analyze_file(
                file_url=file.minio_url,
                filename=file.filename,
                file_type=file.file_type,
                user_query=query
            )
            analyses.append(f"📄 {file.filename}:\n{analysis}")
        except Exception as e:
            logger.error(f"File analysis failed for {file.filename}: {e}")
            analyses.append(f"📄 {file.filename}: خطا در تحلیل فایل")
    
    return "\n\n".join(analyses) if analyses else None


async def stream_query_response(
    request: QueryRequest,
    db: AsyncSession,
    user: UserProfile
) -> AsyncGenerator[str, None]:
    """Generate streaming response for query."""
    start_time = datetime.utcnow()
    
    try:
        # 1. Get or create conversation
        conversation = await get_or_create_conversation(db, user.id, request.conversation_id)
        
        # Send conversation_id first
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': str(conversation.id)}, ensure_ascii=False)}\n\n"
        
        # 2. Analyze files if present
        file_analysis = None
        if request.file_attachments:
            yield f"data: {json.dumps({'type': 'status', 'message': 'در حال تحلیل فایل‌ها...'}, ensure_ascii=False)}\n\n"
            file_analysis = await analyze_files_for_query(request.file_attachments, request.query)
            if file_analysis:
                yield f"data: {json.dumps({'type': 'file_analysis', 'content': file_analysis}, ensure_ascii=False)}\n\n"
        
        # 3. Get conversation memory
        memory_service = get_conversation_memory()
        long_term_memory = await memory_service.get_long_term_memory(
            db, str(user.id), str(conversation.id)
        )
        short_term_memory = await memory_service.get_short_term_memory(
            db, str(conversation.id), limit=10
        )
        
        # 4. Classify query
        if settings.enable_query_classification:
            from app.llm.classifier import QueryClassifier
            classifier = QueryClassifier()
            
            context_for_classification = long_term_memory or ""
            classification = await classifier.classify(
                query=request.query,
                language=request.language,
                context=context_for_classification,
                file_analysis=file_analysis
            )
            
            yield f"data: {json.dumps({'type': 'classification', 'category': classification.category, 'confidence': classification.confidence}, ensure_ascii=False)}\n\n"
            
            # Handle non-business questions
            if classification.category in ["invalid_no_file", "invalid_with_file", "general_no_business"]:
                # Use LLM directly for streaming
                from app.config.prompts import LLMConfig as LLMConfigPresets
                
                llm_config = LLMConfig(
                    provider=LLMProviderEnum.OPENAI_COMPATIBLE,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    **LLMConfigPresets.get_config_for_general_questions()
                )
                llm = OpenAIProvider(llm_config)
                
                # Get current date/time in Shamsi
                tehran_tz = pytz.timezone('Asia/Tehran')
                now = datetime.now(tehran_tz)
                jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
                current_date_shamsi = jalali_now.strftime('%Y/%m/%d')
                current_time_fa = now.strftime('%H:%M')
                
                from app.config.prompts import SystemPrompts
                
                if classification.category == "invalid_no_file":
                    system_msg = SystemPrompts.get_invalid_no_file_prompt(
                        current_date_shamsi=current_date_shamsi,
                        current_time_fa=current_time_fa
                    )
                elif classification.category == "invalid_with_file":
                    if classification.has_meaningful_files:
                        system_msg = SystemPrompts.get_invalid_with_file_meaningful_prompt(
                            current_date_shamsi=current_date_shamsi,
                            current_time_fa=current_time_fa
                        )
                    else:
                        system_msg = SystemPrompts.get_invalid_with_file_meaningless_prompt(
                            current_date_shamsi=current_date_shamsi,
                            current_time_fa=current_time_fa
                        )
                else:  # general_no_business
                    system_msg = SystemPrompts.get_system_identity_short(
                        current_date_shamsi=current_date_shamsi,
                        current_time_fa=current_time_fa
                    )
                
                # Build user message with context for general_no_business
                user_message_parts = []
                
                # 1. Long-term memory
                if long_term_memory:
                    user_message_parts.append(f"[خلاصه مکالمات قبلی]\n{long_term_memory}\n")
                
                # 2. Short-term memory
                if short_term_memory:
                    memory_text = "\n".join([
                        f"{'کاربر' if m['role'] == 'user' else 'دستیار'}: {m['content']}"
                        for m in short_term_memory
                    ])
                    user_message_parts.append(f"[مکالمات اخیر]\n{memory_text}\n")
                
                # 3. File analysis
                if file_analysis:
                    user_message_parts.append(f"[تحلیل فایل‌های ضمیمه]\n{file_analysis}\n")
                
                # 4. Current question
                user_message_parts.append(f"[سوال فعلی]\n{request.query}")
                
                user_message = "\n".join(user_message_parts)
                
                messages = [
                    Message(role="system", content=system_msg),
                    Message(role="user", content=user_message)
                ]
                
                # Stream response
                full_response = ""
                async for chunk in llm.generate_stream(messages):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
                
                # Save messages
                user_msg = DBMessage(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content=request.query,
                    created_at=datetime.utcnow()
                )
                db.add(user_msg)
                
                assistant_msg = DBMessage(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    created_at=datetime.utcnow()
                )
                db.add(assistant_msg)
                
                conversation.message_count += 2
                user.increment_query_count()
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_msg.id), 'processing_time_ms': processing_time, 'sources': []}, ensure_ascii=False)}\n\n"
                return
        
        # 5. Business questions - use RAG with streaming
        yield f"data: {json.dumps({'type': 'status', 'message': 'در حال جستجو در منابع...'}, ensure_ascii=False)}\n\n"
        
        # Build context
        full_context_parts = []
        if long_term_memory:
            full_context_parts.append(f"[خلاصه مکالمات قبلی]\n{long_term_memory}\n")
        if short_term_memory:
            memory_text = "\n".join([
                f"{'کاربر' if m['role'] == 'user' else 'سیستم'}: {m['content']}"
                for m in short_term_memory
            ])
            full_context_parts.append(f"[مکالمات اخیر]\n{memory_text}\n")
        if file_analysis:
            full_context_parts.append(f"[تحلیل فایل‌ها]\n{file_analysis}\n")
        full_context_parts.append(f"[سوال فعلی]\n{request.query}")
        
        llm_context = "\n".join(full_context_parts)
        
        # Use RAG pipeline for retrieval
        from app.rag.pipeline import RAGPipeline, RAGQuery
        
        rag_query = RAGQuery(
            text=request.query,
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            language=request.language,
            max_chunks=request.max_results,
            filters=request.filters,
            use_cache=request.use_cache,
            use_reranking=request.use_reranking,
            user_preferences=request.user_preferences
        )
        
        pipeline = RAGPipeline()
        
        # Get chunks (non-streaming part)
        from app.services.embedding_service import get_embedding_service
        embedder = get_embedding_service()
        query_embedding = embedder.encode([request.query])[0]
        
        chunks = await pipeline._retrieve_chunks(
            query_embedding,
            request.query,
            request.filters,
            limit=request.max_results * 3
        )
        
        if request.use_reranking and len(chunks) > request.max_results:
            chunks = await pipeline._rerank_chunks(request.query, chunks, top_k=request.max_results)
        else:
            chunks = chunks[:request.max_results]
        
        yield f"data: {json.dumps({'type': 'status', 'message': f'{len(chunks)} منبع یافت شد'}, ensure_ascii=False)}\n\n"
        
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[منبع {i}]"
            work_title = chunk.metadata.get("work_title") or chunk.metadata.get("document_title")
            if work_title:
                source_info += f" {work_title}"
            if chunk.metadata.get("unit_number"):
                source_info += f" - ماده {chunk.metadata['unit_number']}"
            context_parts.append(f"{source_info}:\n{chunk.text}")
        
        context = "\n\n".join(context_parts)
        
        # Build messages for streaming
        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
        current_date_shamsi = jalali_now.strftime('%Y/%m/%d')
        current_time_fa = now.strftime('%H:%M')
        
        system_prompt = f"""شما یک دستیار حقوقی و مشاور کسب و کار هستید.

**اطلاعات زمانی فعلی:**
تاریخ شمسی: {current_date_shamsi} - ساعت: {current_time_fa} (وقت تهران)

**توجه:** این تاریخ برای تعیین اعتبار قوانین حیاتی است.

بر اساس اطلاعات مرجع ارائه شده پاسخ دهید. اگر اطلاعات کافی ندارید، صریح بگویید."""
        
        user_message_parts = []
        if llm_context:
            user_message_parts.append(llm_context)
            user_message_parts.append("\n" + "="*50 + "\n")
        user_message_parts.append(f"اطلاعات مرجع از پایگاه داده:\n{context}")
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content="\n".join(user_message_parts))
        ]
        
        # Stream LLM response
        llm_config = LLMConfig(
            provider=LLMProviderEnum.OPENAI_COMPATIBLE,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,
            max_tokens=2000,
        )
        llm = OpenAIProvider(llm_config)
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'در حال تولید پاسخ...'}, ensure_ascii=False)}\n\n"
        
        full_response = ""
        async for chunk in llm.generate_stream(messages):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
        
        # Save messages
        user_message_content = request.query
        if request.file_attachments:
            file_info = "\n[فایل‌های ضمیمه: " + ", ".join([f.filename for f in request.file_attachments]) + "]"
            user_message_content += file_info
        
        user_message = DBMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message_content,
            created_at=datetime.utcnow()
        )
        db.add(user_message)
        
        sources = list(set([
            chunk.metadata.get("work_title") or chunk.metadata.get("document_title") or "Unknown"
            for chunk in chunks
        ]))
        
        assistant_message = DBMessage(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            sources=sources,
            created_at=datetime.utcnow()
        )
        db.add(assistant_message)
        
        conversation.message_count += 2
        user.increment_query_count()
        await db.commit()
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_message.id), 'processing_time_ms': processing_time, 'sources': sources}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming query failed: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@router.post(
    "/stream",
    summary="پردازش سوال با پاسخ استریم",
    description="""
    این API سوال کاربر را پردازش کرده و پاسخ را به صورت استریم (Server-Sent Events) ارسال می‌کند.
    
    **مزایا:**
    - نمایش تدریجی پاسخ به کاربر
    - تجربه کاربری بهتر برای پاسخ‌های طولانی
    - کاهش زمان انتظار ظاهری
    
    **نوع پیام‌ها:**
    - `conversation_id`: شناسه مکالمه
    - `status`: وضعیت پردازش
    - `file_analysis`: تحلیل فایل‌ها
    - `classification`: دسته‌بندی سوال
    - `token`: هر توکن از پاسخ
    - `done`: اتمام پاسخ + منابع
    - `error`: خطا
    
    **مثال استفاده:**
    ```javascript
    const eventSource = new EventSource('/api/v1/query/stream', {
        method: 'POST',
        body: JSON.stringify({query: "قانون کار چیست؟", stream: true})
    });
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'token') {
            console.log(data.content);
        }
    };
    ```
    """
)
async def stream_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Process query with streaming response."""
    # Get user (same logic as non-streaming endpoint)
    result = await db.execute(
        select(UserProfile).where(UserProfile.external_user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user if not exists
        user = UserProfile(
            id=uuid.uuid4(),
            external_user_id=user_id,
            username=f"user_{user_id[:8] if len(user_id) >= 8 else user_id}",
            created_at=datetime.utcnow()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return StreamingResponse(
        stream_query_response(request, db, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
