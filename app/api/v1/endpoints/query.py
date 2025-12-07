"""
Query Processing API Endpoints - Enhanced Version
نسخه پیشرفته با تحلیل فایل، حافظه کوتاه‌مدت و بلندمدت
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import structlog

from app.db.session import get_db
from app.rag.pipeline import RAGPipeline, RAGQuery
from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.core.security import get_current_user_id
from app.config.settings import settings
from app.services.conversation_memory import get_conversation_memory, ConversationMemory
from app.services.long_term_memory import get_long_term_memory_service, LongTermMemoryService

# Import shared utilities
from app.api.v1.endpoints.query_utils import (
    get_current_shamsi_datetime,
    get_or_create_user,
    get_or_create_conversation,
    get_conversation_context,
    build_llm_context,
    process_file_attachments,
    save_conversation_messages,
    classify_query_with_context,
)

logger = structlog.get_logger()
router = APIRouter()

# Initialize memory services
memory_service: ConversationMemory = get_conversation_memory()
long_term_memory_service: LongTermMemoryService = get_long_term_memory_service()


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
        # ========== مرحله 1: احراز هویت ==========
        # NOTE: کنترل محدودیت اشتراک سمت سیستم کاربران انجام می‌شود
        user = await get_or_create_user(db, user_id)
        
        # ========== مرحله 2: مدیریت Conversation ==========
        conversation = await get_or_create_conversation(
            db, user.id, request.conversation_id, request.query[:100]
        )
        
        # ========== مرحله 3: تحلیل فایل‌های ضمیمه (اگر وجود دارد) ==========
        file_analysis, files_content = await process_file_attachments(
            request.file_attachments,
            request.query,
            request.language
        )
        
        # ========== مرحله 4: دریافت حافظه مکالمات ==========
        long_term_memory, short_term_memory, context_for_classification = await get_conversation_context(
            db, str(user.id), str(conversation.id)
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
            # اما اگر context دارد، ممکن است follow-up باشد، پس به general_no_business می‌فرستیم
            if classification.category == "invalid_no_file":
                # اگر memory داریم، احتمالاً follow-up است
                if short_term_memory or long_term_memory:
                    logger.info("invalid_no_file but has memory context - treating as general_no_business")
                    # به جای invalid، به عنوان general_no_business handle می‌کنیم
                    classification.category = "general_no_business"
                else:
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
                logger.info("Handling general_no_business: using LLM1 (Light) without RAG")
                
                # استفاده از LLM1 (Light) برای سوالات ساده
                from app.llm.factory import get_llm_for_category
                from app.llm.base import Message
                from app.config.prompts import SystemPrompts
                
                llm = get_llm_for_category(classification.category)
                
                # دریافت تاریخ و ساعت فعلی (شمسی)
                current_date_shamsi, current_time_fa = get_current_shamsi_datetime()
                
                system_message = SystemPrompts.get_system_identity(
                    current_date_shamsi=current_date_shamsi,
                    current_time_fa=current_time_fa
                )
                
                # ساخت user message با context
                user_message_parts = []
                
                # 1. حافظه بلندمدت
                if long_term_memory:
                    user_message_parts.append(f"[خلاصه مکالمات قبلی]\n{long_term_memory}\n")
                
                # 2. حافظه کوتاه‌مدت
                if short_term_memory:
                    memory_text = "\n".join([
                        f"{'کاربر' if m['role'] == 'user' else 'دستیار'}: {m['content']}"
                        for m in short_term_memory
                    ])
                    user_message_parts.append(f"[مکالمات اخیر]\n{memory_text}\n")
                
                # 3. تحلیل فایل
                if file_analysis:
                    user_message_parts.append(f"[تحلیل فایل‌های ضمیمه]\n{file_analysis}\n")
                
                # 4. سوال فعلی
                user_message_parts.append(f"[سوال فعلی]\n{request.query}")
                
                user_message = "\n".join(user_message_parts)
                
                messages = [
                    Message(role="system", content=system_message),
                    Message(role="user", content=user_message)
                ]
                
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
        
        # Context برای LLM (شامل همه چیز) - استفاده از utility مشترک
        llm_context = build_llm_context(
            request.query,
            long_term_memory,
            short_term_memory,
            file_analysis
        )
        
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
        
        # ========== مرحله 9: به‌روزرسانی حافظه‌ها (Background) ==========
        # 9.1: به‌روزرسانی حافظه چت (خلاصه پیام‌های قدیمی)
        background_tasks.add_task(
            memory_service.update_long_term_memory,
            db,
            str(conversation.id),
            force=False
        )
        
        # 9.2: استخراج حافظه بلندمدت کاربر (اطلاعات پایدار)
        background_tasks.add_task(
            _extract_and_save_user_memory,
            db,
            str(user.id),
            str(conversation.id),
            request.query,
            rag_response.answer,
            context_for_classification
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


async def _extract_and_save_user_memory(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_response: str,
    conversation_context: Optional[str]
):
    """
    استخراج و ذخیره حافظه بلندمدت کاربر (Background Task)
    
    این تابع بعد از هر پاسخ اجرا می‌شود و بررسی می‌کند که آیا
    اطلاعات پایداری برای ذخیره وجود دارد یا خیر.
    """
    try:
        # مرحله 1: استخراج حافظه از پیام
        extraction = await long_term_memory_service.extract_memory_from_message(
            user_message=user_message,
            assistant_response=assistant_response,
            conversation_context=conversation_context
        )
        
        # مرحله 2: اگر حافظه‌ای برای ذخیره وجود دارد
        if extraction.get("should_write_memory") and extraction.get("memory_to_write"):
            # مرحله 3: ادغام با حافظه‌های موجود
            result = await long_term_memory_service.merge_memory(
                db=db,
                user_id=user_id,
                new_memory=extraction["memory_to_write"],
                category=extraction.get("category", "other"),
                conversation_id=conversation_id
            )
            
            logger.info(
                "User memory extraction completed",
                user_id=user_id,
                action=result.get("action"),
                memory_content=extraction["memory_to_write"][:50]
            )
        else:
            logger.debug(
                "No memory to extract from message",
                user_id=user_id
            )
            
    except Exception as e:
        # Background task - فقط لاگ می‌کنیم، خطا نمی‌دهیم
        logger.error(f"Failed to extract user memory: {e}")
