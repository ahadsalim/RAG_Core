"""
Query Processing Utilities
ماژول مشترک برای منطق‌های مشترک بین query.py و query_stream.py
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import pytz
import jdatetime

from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole
from app.services.conversation_memory import get_conversation_memory
from app.services.long_term_memory import get_long_term_memory_service
from app.services.file_processing_service import get_file_processing_service
from app.services.storage_service import get_storage_service
from app.services.file_analysis_service import get_file_analysis_service
from app.config.settings import settings

logger = structlog.get_logger()


# ============================================================================
# Date/Time Utilities
# ============================================================================

def get_current_shamsi_datetime() -> Tuple[str, str]:
    """
    دریافت تاریخ و ساعت فعلی به صورت شمسی
    
    Returns:
        Tuple[current_date_shamsi, current_time_fa]
        مثال: ("1404/09/10", "16:24")
    """
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = datetime.now(tehran_tz)
    jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
    current_date_shamsi = jalali_now.strftime('%Y/%m/%d')
    current_time_fa = now.strftime('%H:%M')
    return current_date_shamsi, current_time_fa


# ============================================================================
# User Management
# ============================================================================

async def get_or_create_user(
    db: AsyncSession,
    external_user_id: str
) -> UserProfile:
    """
    دریافت یا ایجاد کاربر بر اساس external_user_id
    
    Args:
        db: Database session
        external_user_id: شناسه خارجی کاربر
        
    Returns:
        UserProfile instance
    """
    stmt = select(UserProfile).where(UserProfile.external_user_id == external_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = UserProfile(
            id=uuid.uuid4(),
            external_user_id=external_user_id,
            username=f"user_{external_user_id[:8] if len(external_user_id) >= 8 else external_user_id}",
            created_at=datetime.utcnow()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("New user created", external_user_id=external_user_id)
    
    return user


# ============================================================================
# Conversation Management
# ============================================================================

async def get_or_create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: Optional[str],
    title: Optional[str] = None
) -> Conversation:
    """
    دریافت یا ایجاد مکالمه
    
    Args:
        db: Database session
        user_id: شناسه کاربر
        conversation_id: شناسه مکالمه (اختیاری)
        title: عنوان مکالمه جدید
        
    Returns:
        Conversation instance
    """
    if conversation_id:
        try:
            conv_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conv_uuid,
                    Conversation.user_id == user_id
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                return conversation
        except ValueError:
            logger.warning(f"Invalid conversation_id format: {conversation_id}")
    
    # ایجاد مکالمه جدید
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title or "گفتگوی جدید",
        message_count=0,
        total_tokens=0,
        created_at=datetime.utcnow()
    )
    db.add(conversation)
    await db.flush()
    
    logger.info("New conversation created", conversation_id=str(conversation.id))
    return conversation


# ============================================================================
# Memory Management
# ============================================================================

async def get_conversation_context(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    short_term_limit: int = 10
) -> Tuple[Optional[str], List[Dict[str, str]], str]:
    """
    دریافت context کامل مکالمه شامل:
    1. حافظه بلندمدت کاربر (اطلاعات پایدار)
    2. حافظه چت (خلاصه پیام‌های قدیمی این مکالمه)
    3. حافظه کوتاه‌مدت (10 پیام آخر)
    
    Args:
        db: Database session
        user_id: شناسه کاربر
        conversation_id: شناسه مکالمه
        short_term_limit: حداکثر پیام‌های کوتاه‌مدت
        
    Returns:
        Tuple[combined_memory_context, short_term_memory, context_for_classification]
    """
    memory_service = get_conversation_memory()
    long_term_memory_service = get_long_term_memory_service()
    
    # 1. حافظه بلندمدت کاربر (اطلاعات پایدار - مشترک بین همه چت‌ها)
    user_memory_context = await long_term_memory_service.get_memory_context(db, user_id)
    
    # 2. حافظه چت (خلاصه پیام‌های قدیمی این مکالمه)
    chat_summary = await memory_service.get_chat_summary(db, conversation_id)
    
    # 3. حافظه کوتاه‌مدت (10 پیام آخر)
    short_term_memory = await memory_service.get_short_term_memory(
        db, conversation_id, limit=short_term_limit
    )
    
    # ترکیب حافظه‌ها برای context
    combined_parts = []
    
    # حافظه بلندمدت کاربر (اولویت بالا)
    if user_memory_context:
        combined_parts.append(user_memory_context)
    
    # خلاصه چت
    if chat_summary:
        combined_parts.append(f"خلاصه قسمت قبلی این مکالمه:\n{chat_summary}")
    
    combined_memory = "\n\n".join(combined_parts) if combined_parts else None
    
    # ترکیب context برای classification (شامل پیام‌های اخیر هم هست)
    context_parts = []
    if combined_memory:
        context_parts.append(combined_memory)
    if short_term_memory:
        memory_lines = []
        for m in short_term_memory[-5:]:  # فقط 5 پیام آخر برای classification
            role = "کاربر" if m['role'] == 'user' else "دستیار"
            memory_lines.append(f"{role}: {m['content'][:200]}")
        memory_text = "\n".join(memory_lines)
        context_parts.append(f"[مکالمات اخیر]\n{memory_text}")
    
    context_for_classification = "\n\n".join(context_parts) if context_parts else ""
    
    logger.info(
        "Memory retrieved",
        has_user_memory=bool(user_memory_context),
        has_chat_summary=bool(chat_summary),
        short_term_messages=len(short_term_memory)
    )
    
    return combined_memory, short_term_memory, context_for_classification


def build_llm_context(
    query: str,
    long_term_memory: Optional[str] = None,
    short_term_memory: Optional[List[Dict[str, str]]] = None,
    file_analysis: Optional[str] = None
) -> str:
    """
    ساخت context کامل برای LLM
    
    Args:
        query: سوال فعلی
        long_term_memory: حافظه بلندمدت
        short_term_memory: حافظه کوتاه‌مدت
        file_analysis: تحلیل فایل‌ها
        
    Returns:
        Context string برای LLM
    """
    context_parts = []
    
    # 1. حافظه بلندمدت
    if long_term_memory:
        context_parts.append(f"[خلاصه مکالمات قبلی]\n{long_term_memory}\n")
    
    # 2. حافظه کوتاه‌مدت
    if short_term_memory:
        memory_text = "\n".join([
            f"{'کاربر' if m['role'] == 'user' else 'سیستم'}: {m['content']}"
            for m in short_term_memory
        ])
        context_parts.append(f"[مکالمات اخیر]\n{memory_text}\n")
    
    # 3. تحلیل فایل
    if file_analysis:
        context_parts.append(f"[تحلیل فایل‌های ضمیمه]\n{file_analysis}\n")
    
    # 4. سوال فعلی
    context_parts.append(f"[سوال فعلی]\n{query}")
    
    return "\n".join(context_parts)


# ============================================================================
# File Processing
# ============================================================================

async def process_file_attachments(
    file_attachments: List[Any],
    query: str,
    language: str = "fa"
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    پردازش و تحلیل فایل‌های ضمیمه
    
    Args:
        file_attachments: لیست فایل‌های ضمیمه
        query: سوال کاربر
        language: زبان
        
    Returns:
        Tuple[file_analysis, files_content]
    """
    if not file_attachments:
        return None, []
    
    file_processor = get_file_processing_service()
    storage_service = get_storage_service()
    file_analysis_service = get_file_analysis_service()
    
    files_content = []
    
    for attachment in file_attachments:
        try:
            # دانلود از MinIO
            file_data = await storage_service.download_temp_file(
                attachment.minio_url
            )
            
            # استخراج متن
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
            logger.error(f"Failed to process file: {e}", filename=attachment.filename)
            continue
    
    # تحلیل فایل‌ها با LLM
    file_analysis = None
    if files_content:
        file_analysis = await file_analysis_service.analyze_files(
            files_content,
            query,
            language
        )
        logger.info(
            "Files analyzed with LLM",
            file_count=len(files_content),
            analysis_length=len(file_analysis) if file_analysis else 0
        )
    
    return file_analysis, files_content


# ============================================================================
# Message Management
# ============================================================================

async def save_conversation_messages(
    db: AsyncSession,
    conversation: Conversation,
    user: UserProfile,
    user_query: str,
    assistant_response: str,
    file_attachments: Optional[List[Any]] = None,
    sources: Optional[List[str]] = None,
    tokens_used: int = 0,
    processing_time_ms: Optional[int] = None,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    model_used: Optional[str] = None
) -> Tuple[DBMessage, DBMessage]:
    """
    ذخیره پیام‌های کاربر و دستیار در دیتابیس
    
    Args:
        db: Database session
        conversation: مکالمه
        user: کاربر
        user_query: سوال کاربر
        assistant_response: پاسخ دستیار
        file_attachments: فایل‌های ضمیمه
        sources: منابع
        tokens_used: توکن‌های مصرفی
        processing_time_ms: زمان پردازش
        retrieved_chunks: چانک‌های بازیابی شده
        model_used: مدل استفاده شده
        
    Returns:
        Tuple[user_message, assistant_message]
    """
    # محتوای پیام کاربر
    user_message_content = user_query
    if file_attachments:
        file_info = "\n[فایل‌های ضمیمه: " + ", ".join(
            [f.filename for f in file_attachments]
        ) + "]"
        user_message_content += file_info
    
    # پیام کاربر
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
        content=assistant_response,
        tokens=tokens_used,
        processing_time_ms=processing_time_ms,
        retrieved_chunks=retrieved_chunks,
        sources=sources,
        model_used=model_used,
        created_at=datetime.utcnow()
    )
    db.add(assistant_message)
    
    # به‌روزرسانی conversation
    conversation.message_count += 2
    conversation.total_tokens += tokens_used
    conversation.last_message_at = datetime.utcnow()
    
    # به‌روزرسانی user
    user.increment_query_count()
    user.total_tokens_used += tokens_used
    
    await db.commit()
    
    return user_message, assistant_message


# ============================================================================
# Classification Helpers
# ============================================================================

async def classify_query_with_context(
    query: str,
    language: str,
    context: str,
    file_analysis: Optional[str],
    short_term_memory: List[Dict[str, str]],
    long_term_memory: Optional[str]
) -> Any:
    """
    کلاسیفیکیشن سوال با در نظر گرفتن context
    
    Args:
        query: سوال کاربر
        language: زبان
        context: context برای classification
        file_analysis: تحلیل فایل
        short_term_memory: حافظه کوتاه‌مدت
        long_term_memory: حافظه بلندمدت
        
    Returns:
        QueryCategory instance
    """
    from app.llm.classifier import QueryClassifier
    
    classifier = QueryClassifier()
    classification = await classifier.classify(
        query=query,
        language=language,
        context=context,
        file_analysis=file_analysis
    )
    
    # اگر invalid_no_file است اما memory دارد، به general_no_business تبدیل می‌کنیم
    if classification.category == "invalid_no_file" and (short_term_memory or long_term_memory):
        logger.info("invalid_no_file but has memory context - treating as general_no_business")
        classification.category = "general_no_business"
    
    logger.info(
        "Query classified",
        category=classification.category,
        confidence=classification.confidence,
        has_meaningful_files=classification.has_meaningful_files,
        needs_clarification=classification.needs_clarification
    )
    
    return classification
