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

# ============================================================================
# DEBUG MODE - اضافه کردن اطلاعات دیباگ به ابتدای پاسخ (موقت برای تست)
# ============================================================================
DEBUG_MODE = True  # برای غیرفعال کردن، False کنید

def add_debug_info(
    answer: str,
    category: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    confidence: float = 0.0,
    cached: bool = False,
    reranker_details: list = None
) -> str:
    """
    اضافه کردن اطلاعات دیباگ به ابتدای پاسخ (موقت برای تست)
    """
    if not DEBUG_MODE:
        return answer
    
    # اگر از cache آمده، توکن‌ها صفر هستند (هزینه‌ای نداریم)
    if cached:
        token_info = "💾 از کش (بدون هزینه توکن)"
    else:
        token_info = f"📥 توکن ورودی: `{input_tokens}` | 📤 توکن خروجی: `{output_tokens}`"
    
    # اطلاعات کامل reranker
    reranker_info = ""
    if reranker_details:
        reranker_lines = ["\n🔄 **Reranker Results (همه chunks):**"]
        for i, detail in enumerate(reranker_details):
            score = detail.get("score", 0)
            source = detail.get("source", "?")[:40]
            unit = detail.get("unit", "")
            # نشانه‌گذاری top 5 که به LLM داده شدند
            marker = "✅" if i < 5 else "❌"
            reranker_lines.append(f"  {marker} #{i+1}: `{score:.4f}` | {source} | ماده {unit}")
        reranker_info = "\n".join(reranker_lines)
    
    debug_header = f"""📊 **[DEBUG INFO]**
🏷️ دسته: `{category}` | اطمینان: `{confidence:.0%}`
🤖 مدل: `{model}`
{token_info}{reranker_info}
---

"""
    return debug_header + answer

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
    max_results: int = Field(default=settings.rag_max_chunks, ge=1, le=20)
    filters: Optional[Dict[str, Any]] = None
    use_cache: bool = True
    use_reranking: bool = True
    user_preferences: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[FileAttachment]] = Field(None, max_items=5)
    enable_web_search: Optional[bool] = Field(
        default=None, 
        description="Enable web search for RAG responses. If None, uses server default (ENABLE_RAG_WEB_SEARCH). Set to True/False to override."
    )


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
            
            # ========== هندل اطمینان پایین ==========
            # اگر اطمینان زیر 50% است، درخواست توضیح کن
            # توجه: needs_clarification برای invalid ها طبیعی است و جداگانه هندل می‌شود
            if classification.confidence < 0.5 and classification.category not in ["invalid_no_file", "invalid_with_file"]:
                logger.info(
                    "Low confidence or needs clarification",
                    confidence=classification.confidence,
                    needs_clarification=classification.needs_clarification,
                    original_category=classification.category
                )
                
                # پاسخ درخواست توضیح
                clarification_response = classification.direct_response or "متوجه منظور شما نشدم. لطفاً سوال یا درخواست خود را واضح‌تر بیان کنید."
                
                # اضافه کردن اطلاعات دیباگ
                clarification_response = add_debug_info(
                    answer=clarification_response,
                    category=f"{classification.category} (low_confidence)",
                    model="classifier",
                    input_tokens=0,
                    output_tokens=0,
                    confidence=classification.confidence
                )
                
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
                    content=clarification_response,
                    created_at=datetime.utcnow()
                )
                db.add(assistant_msg)
                
                conversation.message_count += 2
                user.increment_query_count()
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return QueryResponse(
                    answer=clarification_response,
                    sources=[],
                    conversation_id=str(conversation.id),
                    message_id=str(assistant_msg.id),
                    tokens_used=0,
                    processing_time_ms=processing_time,
                    file_analysis=file_analysis,
                    context_used=bool(short_term_memory or long_term_memory)
                )
            
            # ========== مسیر 1: invalid_no_file - متن نامعتبر بدون فایل ==========
            if classification.category == "invalid_no_file":
                logger.info("Handling invalid_no_file: asking for clarification")
                
                response_text = classification.direct_response or "متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح و کامل بپرسید."
                
                # اضافه کردن اطلاعات دیباگ
                response_text = add_debug_info(
                    answer=response_text,
                    category=classification.category,
                    model="classifier",
                    input_tokens=0,
                    output_tokens=0,
                    confidence=classification.confidence
                )
                
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
                
                # اضافه کردن اطلاعات دیباگ
                response_text = add_debug_info(
                    answer=response_text,
                    category=classification.category,
                    model="classifier",
                    input_tokens=0,
                    output_tokens=0,
                    confidence=classification.confidence
                )
                
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
            
            # ========== مسیر 3: general - سوال عمومی غیر کسب‌وکار ==========
            elif classification.category == "general":
                logger.info(
                    "Handling general: using LLM1 (Light) without RAG",
                    needs_web_search=classification.needs_web_search
                )
                
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
                
                # استخراج تصاویر از files_content
                images_for_llm = []
                if files_content:
                    for fc in files_content:
                        if fc.get('is_image') and fc.get('image_data'):
                            images_for_llm.append({
                                'data': fc['image_data'],
                                'filename': fc['filename']
                            })
                
                # انتخاب روش پاسخ‌دهی
                if images_for_llm:
                    # اگر تصویر داریم، از Vision API استفاده کن
                    logger.info("Using Vision API for general query with images", image_count=len(images_for_llm))
                    llm_response = await llm.generate_with_images(messages, images_for_llm)
                    model_used = f"{settings.llm1_model} (vision)"
                elif classification.needs_web_search:
                    logger.info("Using web search for general query")
                    llm_response = await llm.generate_with_web_search(messages)
                    model_used = f"{settings.llm1_model} (web_search)"
                else:
                    llm_response = await llm.generate_responses_api(
                        messages,
                        reasoning_effort="low"
                    )
                    model_used = settings.llm1_model
                response_text = llm_response.content
                
                # اضافه کردن اطلاعات دیباگ
                response_text = add_debug_info(
                    answer=response_text,
                    category=classification.category,
                    model=model_used,
                    input_tokens=llm_response.usage.get("prompt_tokens", 0) if llm_response.usage else 0,
                    output_tokens=llm_response.usage.get("completion_tokens", 0) if llm_response.usage else 0,
                    confidence=classification.confidence
                )
                
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
                
                # به‌روزرسانی توکن‌های کاربر
                input_tokens = llm_response.usage.get("prompt_tokens", 0) if llm_response.usage else 0
                output_tokens = llm_response.usage.get("completion_tokens", 0) if llm_response.usage else 0
                total_tokens = llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0
                user.total_tokens_used += total_tokens
                user.total_input_tokens += input_tokens
                user.total_output_tokens += output_tokens
                
                await db.commit()
                
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return QueryResponse(
                    answer=response_text,
                    sources=[],
                    conversation_id=str(conversation.id),
                    message_id=str(assistant_msg.id),
                    tokens_used=total_tokens,
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
        # تعیین وضعیت web search:
        # 1. Classifier تصمیم نهایی را می‌گیرد (needs_web_search)
        # 2. اگر کاربر enable_web_search=false فرستاده، حتی اگر classifier بگوید true، غیرفعال می‌شود
        # 3. اگر کاربر enable_web_search=true فرستاده ولی classifier بگوید false، غیرفعال می‌ماند (classifier اولویت دارد)
        # 4. اگر کاربر چیزی نفرستاده، فقط تصمیم classifier ملاک است
        
        # تصمیم classifier
        classifier_wants_web_search = classification.needs_web_search
        
        # تصمیم نهایی: classifier باید بگوید نیاز است AND کاربر نباید صریحاً غیرفعال کرده باشد
        # همچنین بررسی می‌کنیم که آیا کاربر جستجوی وب را غیرفعال کرده در حالی که نیاز بود
        web_search_blocked_by_user = False
        
        if request.enable_web_search is False:
            # کاربر صریحاً غیرفعال کرده
            web_search_enabled = False
            if classifier_wants_web_search:
                # classifier می‌گوید نیاز است ولی کاربر غیرفعال کرده
                web_search_blocked_by_user = True
        else:
            # classifier تصمیم می‌گیرد
            web_search_enabled = classifier_wants_web_search
        
        logger.info(
            "Web search decision",
            classifier_decision=classifier_wants_web_search,
            user_preference=request.enable_web_search,
            final_decision=web_search_enabled
        )
        
        # استخراج تصاویر از files_content برای ارسال به LLM
        images_for_rag = []
        if files_content:
            for fc in files_content:
                if fc.get('is_image') and fc.get('image_data'):
                    images_for_rag.append({
                        'data': fc['image_data'],
                        'filename': fc['filename']
                    })
        
        rag_query = RAGQuery(
            text=search_query,  # فقط سوال اصلی برای embedding
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            language=request.language,
            max_chunks=request.max_results,
            filters=request.filters,
            use_cache=request.use_cache,
            use_reranking=request.use_reranking,
            user_preferences=request.user_preferences,
            enable_web_search=web_search_enabled,  # Web search بر اساس تصمیم classifier و ترجیح کاربر
            # فیلتر زمانی بر اساس تشخیص classifier
            temporal_context=classification.temporal_context if classification else None,
            target_date=classification.target_date if classification else None,
            # تصاویر برای Vision API
            images=images_for_rag if images_for_rag else None
        )
        
        pipeline = RAGPipeline()
        rag_response = await pipeline.process(
            rag_query,
            additional_context=llm_context,  # Context کامل برای LLM
            skip_classification=True  # Classification قبلاً انجام شده
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
        user.total_input_tokens += rag_response.input_tokens
        user.total_output_tokens += rag_response.output_tokens
        
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
        
        # اضافه کردن اطلاعات دیباگ به پاسخ RAG
        model_display = rag_response.model_used or settings.llm2_model
        if web_search_enabled:
            model_display = f"{model_display} (web_search)"
        
        # اضافه کردن پیام هشدار اگر کاربر جستجوی وب را غیرفعال کرده در حالی که نیاز بود
        answer_with_warning = rag_response.answer
        if web_search_blocked_by_user:
            web_search_warning = "\n\n---\n⚠️ **توجه:** برای پاسخ دقیق‌تر به این سوال، نیاز به جستجوی اینترنت بود که در تنظیمات شما غیرفعال است. برای دریافت اطلاعات به‌روزتر، لطفاً جستجوی وب را در تنظیمات فعال کنید."
            answer_with_warning = rag_response.answer + web_search_warning
        
        final_answer = add_debug_info(
            answer=answer_with_warning,
            category=classification.category,
            model=model_display,
            input_tokens=rag_response.input_tokens,
            output_tokens=rag_response.output_tokens,
            confidence=classification.confidence,
            cached=rag_response.cached,
            reranker_details=rag_response.reranker_details
        )
        
        return QueryResponse(
            answer=final_answer,
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
