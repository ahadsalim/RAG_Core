"""
Query Processing API Endpoints - Enhanced Version
نسخه پیشرفته با تحلیل فایل، حافظه کوتاه‌مدت و بلندمدت
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, validator
import structlog

from app.db.session import get_db
from app.rag.pipeline import RAGPipeline, RAGQuery
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.core.dependencies import get_redis_client
from app.config.settings import settings
from app.services.file_processing_service import get_file_processing_service
from app.services.storage_service import get_storage_service
from app.services.file_analysis_service import get_file_analysis_service
from app.services.conversation_memory import get_conversation_memory

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models (same as before)
class FileAttachment(BaseModel):
    """File attachment model with MinIO link."""
    filename: str = Field(..., description="Original filename")
    minio_url: str = Field(..., description="MinIO object key or full URL")
    file_type: str = Field(..., description="MIME type")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")


class QueryRequest(BaseModel):
    """Query request model with file attachments."""
    query: str = Field(..., min_length=1, max_length=settings.max_query_length)
    conversation_id: Optional[str] = None
    language: str = Field(default="fa", pattern="^(fa|en|ar)$")
    max_results: int = Field(default=5, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = None
    use_cache: bool = True
    use_reranking: bool = True
    stream: bool = False
    user_preferences: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[FileAttachment]] = Field(None, max_items=5)


class QueryResponse(BaseModel):
    """Query response model."""
    answer: str
    sources: list[str]
    conversation_id: str
    message_id: str
    tokens_used: int
    processing_time_ms: int
    file_analysis: Optional[str] = None  # تحلیل فایل‌ها
    context_used: bool = False  # آیا از حافظه استفاده شد


@router.post(
    "/",
    response_model=QueryResponse,
    summary="پردازش سوال کاربر با قابلیت‌های پیشرفته",
    description="""
    این API سوال کاربر را پردازش می‌کند با قابلیت‌های:
    
    **1. تحلیل فایل با LLM:**
    - اگر فایل ضمیمه شده باشد، ابتدا با LLM تحلیل می‌شود
    - پشتیبانی از تصویر، PDF، TXT
    - استخراج اطلاعات کلیدی از فایل
    
    **2. حافظه کوتاه‌مدت:**
    - 10 پیام آخر مکالمه در نظر گرفته می‌شود
    - برای پاسخ به سوالات پیوسته
    
    **3. حافظه بلندمدت:**
    - خلاصه مکالمات قبلی کاربر
    - به‌روزرسانی خودکار بعد از 20 پیام
    
    **4. کلاسیفیکیشن هوشمند:**
    - با در نظر گرفتن context و فایل‌ها
    - تشخیص سوال واقعی از چرت‌وپرت
    
    **5. تولید پاسخ:**
    - با استفاده از تمام context
    - پاسخ دقیق و مرتبط
    """
)
async def process_query_enhanced(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> QueryResponse:
    """پردازش سوال با قابلیت‌های پیشرفته"""
    
    start_time = datetime.utcnow()
    
    try:
        # ========== مرحله 1: احراز هویت و بررسی محدودیت‌ها ==========
        stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = UserProfile(
                id=uuid.uuid4(),
                external_user_id=user_id,
                username=f"user_{user_id[:8]}",
                created_at=datetime.utcnow()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        if not user.can_make_query():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily query limit exceeded"
            )
        
        # ========== مرحله 2: مدیریت Conversation ==========
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
        
        # ========== مرحله 3: تحلیل فایل‌های ضمیمه (اگر وجود دارد) ==========
        file_analysis = None
        file_context = ""
        
        if request.file_attachments:
            logger.info(
                f"Processing {len(request.file_attachments)} file attachments",
                user_id=user_id,
                conversation_id=str(conversation.id)
            )
            
            # دانلود و استخراج محتوای فایل‌ها
            file_processor = get_file_processing_service()
            storage_service = get_storage_service()
            file_analysis_service = get_file_analysis_service()
            
            files_content = []
            for attachment in request.file_attachments:
                try:
                    # دانلود از MinIO
                    file_data = await storage_service.download_temp_file(
                        attachment.minio_url
                    )
                    
                    # استخراج متن (OCR برای تصویر، text extraction برای PDF)
                    processing_result = await file_processor.process_file(
                        file_data,
                        attachment.filename,
                        attachment.file_type
                    )
                    
                    files_content.append({
                        'filename': attachment.filename,
                        'file_type': attachment.file_type,
                        'content': processing_result.get('text', ''),
                        'is_image': attachment.file_type.startswith('image/')
                    })
                    
                except Exception as e:
                    logger.error(
                        f"Failed to process file: {e}",
                        filename=attachment.filename
                    )
                    continue
            
            # تحلیل فایل‌ها با LLM
            if files_content:
                file_analysis = await file_analysis_service.analyze_files(
                    files_content,
                    request.query,
                    request.language
                )
                
                logger.info(
                    "Files analyzed with LLM",
                    file_count=len(files_content),
                    analysis_length=len(file_analysis)
                )
        
        # ========== مرحله 4: دریافت حافظه مکالمات ==========
        memory_service = get_conversation_memory()
        
        # حافظه بلندمدت (خلاصه مکالمات قبلی)
        long_term_memory = await memory_service.get_long_term_memory(
            db,
            str(user.id),
            str(conversation.id)
        )
        
        # حافظه کوتاه‌مدت (پیام‌های اخیر)
        short_term_memory = await memory_service.get_short_term_memory(
            db,
            str(conversation.id),
            limit=10
        )
        
        # ترکیب context برای classification
        context_for_classification = ""
        if long_term_memory:
            context_for_classification = long_term_memory
        
        logger.info(
            "Memory retrieved",
            has_long_term=bool(long_term_memory),
            short_term_messages=len(short_term_memory)
        )
        
        # ========== مرحله 5: کلاسیفیکیشن دقیق سوال ==========
        classification = None
        
        if settings.enable_query_classification:
            from app.llm.classifier import QueryClassifier
            classifier = QueryClassifier()
            
            classification = await classifier.classify(
                query=request.query,
                language=request.language,
                context=context_for_classification,
                file_analysis=file_analysis
            )
            
            logger.info(
                "Query classified",
                category=classification.category,
                confidence=classification.confidence,
                has_meaningful_files=classification.has_meaningful_files,
                needs_clarification=classification.needs_clarification
            )
            
            # ========== مسیر 1: invalid_no_file - متن نامعتبر بدون فایل ==========
            if classification.category == "invalid_no_file":
                logger.info("Handling invalid_no_file: asking for clarification")
                
                response_text = classification.direct_response or "متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح و کامل بپرسید."
                
                # ذخیره در دیتابیس
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
                    content=response_text,
                    created_at=datetime.utcnow()
                )
                db.add(assistant_msg)
                
                conversation.message_count += 2
                user.increment_query_count()
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return QueryResponse(
                    answer=response_text,
                    sources=[],
                    conversation_id=str(conversation.id),
                    message_id=str(assistant_msg.id),
                    tokens_used=0,
                    processing_time_ms=processing_time,
                    file_analysis=None,
                    context_used=False
                )
            
            # ========== مسیر 2: invalid_with_file - متن مبهم با فایل ==========
            elif classification.category == "invalid_with_file":
                logger.info(
                    "Handling invalid_with_file",
                    has_meaningful_files=classification.has_meaningful_files
                )
                
                # اگر فایل معنادار است، سوال هوشمندانه بپرس
                # اگر فایل بی‌معنی است، درخواست توضیح کن
                response_text = classification.direct_response or "لطفاً سوال خود را واضح‌تر بیان کنید."
                
                # ذخیره در دیتابیس
                user_msg = DBMessage(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content=f"{request.query}\n[فایل‌های ضمیمه: {', '.join([f.filename for f in request.file_attachments])}]" if request.file_attachments else request.query,
                    created_at=datetime.utcnow()
                )
                db.add(user_msg)
                
                assistant_msg = DBMessage(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                    created_at=datetime.utcnow()
                )
                db.add(assistant_msg)
                
                conversation.message_count += 2
                user.increment_query_count()
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return QueryResponse(
                    answer=response_text,
                    sources=[],
                    conversation_id=str(conversation.id),
                    message_id=str(assistant_msg.id),
                    tokens_used=0,
                    processing_time_ms=processing_time,
                    file_analysis=file_analysis,
                    context_used=False
                )
            
            # ========== مسیر 3: general_no_business - سوال عمومی غیر کسب‌وکار ==========
            elif classification.category == "general_no_business":
                logger.info("Handling general_no_business: using LLM without RAG")
                
                # استفاده از LLM به صورت عمومی (بدون RAG)
                from app.llm.openai_provider import OpenAIProvider
                from app.llm.base import LLMConfig, LLMProvider as LLMProviderEnum, Message
                import pytz
                
                llm_config = LLMConfig(
                    provider=LLMProviderEnum.OPENAI_COMPATIBLE,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    temperature=0.7,
                    max_tokens=1000,
                )
                llm = OpenAIProvider(llm_config)
                
                # دریافت تاریخ و ساعت فعلی
                tehran_tz = pytz.timezone('Asia/Tehran')
                now = datetime.now(tehran_tz)
                current_date_fa = now.strftime('%Y/%m/%d')
                current_time_fa = now.strftime('%H:%M')
                
                # ساخت پیام‌ها با تاریخ و ساعت
                system_message = f"""شما یک دستیار هوشمند و دوستانه هستید که به سوالات عمومی کاربران پاسخ می‌دهید.

**اطلاعات زمانی فعلی:**
تاریخ: {current_date_fa} - ساعت: {current_time_fa}

از این اطلاعات برای پاسخ به سوالات مرتبط با زمان استفاده کنید."""
                
                messages = [
                    Message(role="system", content=system_message),
                    Message(role="user", content=request.query)
                ]
                
                # اگر فایل دارد، اضافه کن
                if file_analysis:
                    messages.append(
                        Message(role="user", content=f"تحلیل فایل‌های ضمیمه:\n{file_analysis}")
                    )
                
                llm_response = await llm.generate(messages)
                response_text = llm_response.content
                
                # ذخیره در دیتابیس
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
                    content=response_text,
                    created_at=datetime.utcnow()
                )
                db.add(assistant_msg)
                
                conversation.message_count += 2
                user.increment_query_count()
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return QueryResponse(
                    answer=response_text,
                    sources=[],
                    conversation_id=str(conversation.id),
                    message_id=str(assistant_msg.id),
                    tokens_used=llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0,
                    processing_time_ms=processing_time,
                    file_analysis=file_analysis,
                    context_used=False
                )
            
            # ========== مسیر 4 و 5: business_no_file و business_with_file ==========
            # این دو مسیر به RAG Pipeline می‌روند (ادامه کد فعلی)
        
        # ========== مرحله 6: ساخت Query و Context برای RAG ==========
        # برای جلوگیری از hallucination:
        # - Query برای embedding: فقط سوال اصلی (بدون context)
        # - Context برای LLM: شامل حافظه + فایل + سوال
        
        # Query برای جستجو (فقط سوال اصلی)
        search_query = request.query
        
        # Context برای LLM (شامل همه چیز)
        full_context_parts = []
        
        # 1. حافظه بلندمدت
        if long_term_memory:
            full_context_parts.append(f"[خلاصه مکالمات قبلی]\n{long_term_memory}\n")
        
        # 2. حافظه کوتاه‌مدت (پیام‌های اخیر)
        if short_term_memory:
            memory_text = "\n".join([
                f"{'کاربر' if m['role'] == 'user' else 'سیستم'}: {m['content']}"
                for m in short_term_memory
            ])
            full_context_parts.append(f"[مکالمات اخیر]\n{memory_text}\n")
        
        # 3. تحلیل فایل
        if file_analysis:
            full_context_parts.append(f"[تحلیل فایل‌های ضمیمه]\n{file_analysis}\n")
        
        # 4. سوال فعلی
        full_context_parts.append(f"[سوال فعلی]\n{request.query}")
        
        llm_context = "\n".join(full_context_parts)
        
        logger.info(
            "RAG query prepared",
            search_query_length=len(search_query),
            llm_context_length=len(llm_context),
            has_file_analysis=bool(file_analysis),
            has_memory=bool(long_term_memory or short_term_memory)
        )
        
        # ========== مرحله 7: پردازش با RAG Pipeline ==========
        rag_query = RAGQuery(
            text=search_query,  # فقط سوال اصلی برای embedding
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
        rag_response = await pipeline.process(
            rag_query,
            additional_context=llm_context  # Context کامل برای LLM
        )
        
        # ========== مرحله 8: ذخیره پیام‌ها ==========
        # پیام کاربر
        user_message_content = request.query
        if request.file_attachments:
            file_info = "\n[فایل‌های ضمیمه: " + ", ".join(
                [f.filename for f in request.file_attachments]
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
        
        # پیام دستیار
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
        
        # به‌روزرسانی conversation
        conversation.message_count += 2
        conversation.total_tokens += rag_response.total_tokens
        conversation.last_message_at = datetime.utcnow()
        
        # به‌روزرسانی user
        user.increment_query_count()
        user.total_tokens_used += rag_response.total_tokens
        
        await db.commit()
        
        # ========== مرحله 9: به‌روزرسانی حافظه بلندمدت (Background) ==========
        background_tasks.add_task(
            memory_service.update_long_term_memory,
            db,
            str(conversation.id),
            force=False
        )
        
        # ========== مرحله 10: برگرداندن پاسخ ==========
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return QueryResponse(
            answer=rag_response.answer,
            sources=rag_response.sources,
            conversation_id=str(conversation.id),
            message_id=str(assistant_message.id),
            tokens_used=rag_response.total_tokens,
            processing_time_ms=processing_time,
            file_analysis=file_analysis,
            context_used=bool(long_term_memory or short_term_memory)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )
