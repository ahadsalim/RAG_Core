"""
Conversation Memory Service
مدیریت حافظه کوتاه‌مدت و بلندمدت مکالمات
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import structlog

from app.models.user import Conversation, Message as DBMessage, MessageRole
from app.llm.base import LLMConfig, LLMProvider, Message
from app.llm.openai_provider import OpenAIProvider
from app.config.settings import settings

logger = structlog.get_logger()


class ConversationMemory:
    """مدیریت حافظه مکالمات"""
    
    # تنظیمات حافظه
    SHORT_TERM_MESSAGES = 10  # تعداد پیام‌های اخیر برای حافظه کوتاه‌مدت
    LONG_TERM_MAX_CHARS = 2000  # حداکثر طول حافظه بلندمدت قبل از خلاصه‌سازی
    SUMMARY_TRIGGER_MESSAGES = 20  # تعداد پیام‌ها برای trigger خلاصه‌سازی
    
    def __init__(self):
        """Initialize memory service with LLM for summarization"""
        self.llm_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,
            max_tokens=500,
        )
        self.llm = OpenAIProvider(self.llm_config)
        logger.info("ConversationMemory initialized")
    
    async def get_short_term_memory(
        self,
        db: AsyncSession,
        conversation_id: str,
        limit: int = None
    ) -> List[Dict[str, str]]:
        """
        دریافت حافظه کوتاه‌مدت (پیام‌های اخیر)
        
        Args:
            db: Database session
            conversation_id: ID مکالمه
            limit: تعداد پیام‌ها (پیش‌فرض: SHORT_TERM_MESSAGES)
            
        Returns:
            لیست پیام‌ها به فرمت [{"role": "user", "content": "..."}, ...]
        """
        limit = limit or self.SHORT_TERM_MESSAGES
        
        try:
            # دریافت پیام‌های اخیر
            result = await db.execute(
                select(DBMessage)
                .filter(DBMessage.conversation_id == conversation_id)
                .order_by(desc(DBMessage.created_at))
                .limit(limit)
            )
            messages = result.scalars().all()
            
            # تبدیل به فرمت مناسب (معکوس برای ترتیب زمانی)
            memory = []
            for msg in reversed(messages):
                memory.append({
                    "role": "user" if msg.role == MessageRole.USER else "assistant",
                    "content": msg.content
                })
            
            logger.info(
                "Short-term memory retrieved",
                conversation_id=conversation_id,
                message_count=len(memory)
            )
            
            return memory
            
        except Exception as e:
            logger.error(f"Failed to get short-term memory: {e}")
            return []
    
    async def get_long_term_memory(
        self,
        db: AsyncSession,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> Optional[str]:
        """
        دریافت حافظه بلندمدت (خلاصه مکالمات قبلی)
        
        Args:
            db: Database session
            user_id: ID کاربر
            conversation_id: ID مکالمه فعلی (برای exclude کردن)
            
        Returns:
            خلاصه مکالمات قبلی یا None
        """
        try:
            # دریافت مکالمه فعلی
            query = select(Conversation).filter(
                Conversation.user_id == user_id
            )
            
            if conversation_id:
                query = query.filter(Conversation.id == conversation_id)
            
            result = await db.execute(query)
            conversation = result.scalar_one_or_none()
            
            if conversation and conversation.summary:
                logger.info(
                    "Long-term memory retrieved",
                    user_id=user_id,
                    summary_length=len(conversation.summary)
                )
                return conversation.summary
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get long-term memory: {e}")
            return None
    
    async def update_long_term_memory(
        self,
        db: AsyncSession,
        conversation_id: str,
        force: bool = False
    ) -> bool:
        """
        به‌روزرسانی حافظه بلندمدت (خلاصه‌سازی)
        
        Args:
            db: Database session
            conversation_id: ID مکالمه
            force: اجبار به خلاصه‌سازی حتی اگر شرایط فراهم نباشد
            
        Returns:
            True اگر خلاصه‌سازی انجام شد
        """
        try:
            # دریافت مکالمه
            result = await db.execute(
                select(Conversation).filter(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return False
            
            # دریافت تعداد پیام‌ها
            result = await db.execute(
                select(DBMessage)
                .filter(DBMessage.conversation_id == conversation_id)
            )
            messages = result.scalars().all()
            message_count = len(messages)
            
            # بررسی نیاز به خلاصه‌سازی
            current_summary_length = len(conversation.summary or "")
            
            if not force:
                # خلاصه‌سازی فقط اگر:
                # 1. تعداد پیام‌ها بیش از حد باشد
                # 2. یا خلاصه فعلی خیلی طولانی باشد
                if (message_count < self.SUMMARY_TRIGGER_MESSAGES and 
                    current_summary_length < self.LONG_TERM_MAX_CHARS):
                    return False
            
            # تهیه متن برای خلاصه‌سازی
            conversation_text = self._prepare_conversation_for_summary(
                messages,
                conversation.summary
            )
            
            # خلاصه‌سازی با LLM
            new_summary = await self._summarize_conversation(conversation_text)
            
            if new_summary:
                # ذخیره خلاصه جدید
                conversation.summary = new_summary
                conversation.updated_at = datetime.utcnow()
                await db.commit()
                
                logger.info(
                    "Long-term memory updated",
                    conversation_id=conversation_id,
                    message_count=message_count,
                    summary_length=len(new_summary)
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update long-term memory: {e}")
            await db.rollback()
            return False
    
    def _prepare_conversation_for_summary(
        self,
        messages: List[DBMessage],
        existing_summary: Optional[str]
    ) -> str:
        """تهیه متن مکالمه برای خلاصه‌سازی"""
        parts = []
        
        # اضافه کردن خلاصه قبلی
        if existing_summary:
            parts.append(f"خلاصه قبلی:\n{existing_summary}\n")
        
        # اضافه کردن پیام‌های جدید
        parts.append("مکالمات جدید:")
        for msg in messages[-self.SUMMARY_TRIGGER_MESSAGES:]:
            role = "کاربر" if msg.role == MessageRole.USER else "سیستم"
            parts.append(f"{role}: {msg.content}")
        
        return "\n".join(parts)
    
    async def _summarize_conversation(self, conversation_text: str) -> Optional[str]:
        """خلاصه‌سازی مکالمه با LLM"""
        try:
            system_prompt = """تو یک دستیار هوشمند هستی که وظیفه‌ات خلاصه کردن مکالمات است.
از مکالمه داده شده، موارد مهم زیر را استخراج کن:
1. موضوعات اصلی که کاربر در موردشان سوال پرسیده
2. اطلاعات مهم درباره کاربر (نیازها، ترجیحات، زمینه کاری)
3. نتایج و پاسخ‌های کلیدی

خلاصه را به صورت مختصر و مفید بنویس (حداکثر 300 کلمه).
فقط خلاصه را بنویس، بدون توضیحات اضافی."""

            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=conversation_text)
            ]
            
            response = await self.llm.generate(messages)
            summary = response.content  # Extract content from LLMResponse
            
            logger.info(
                "Conversation summarized",
                input_length=len(conversation_text),
                summary_length=len(summary)
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return None
    
    async def build_context_for_llm(
        self,
        db: AsyncSession,
        user_id: str,
        conversation_id: Optional[str],
        current_query: str,
        file_analysis: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        ساخت context کامل برای LLM شامل:
        - حافظه بلندمدت
        - حافظه کوتاه‌مدت
        - تحلیل فایل (اگر وجود دارد)
        - سوال فعلی
        
        Args:
            db: Database session
            user_id: ID کاربر
            conversation_id: ID مکالمه
            current_query: سوال فعلی
            file_analysis: تحلیل فایل ضمیمه شده
            
        Returns:
            لیست پیام‌ها برای LLM
        """
        context = []
        
        # 1. حافظه بلندمدت (خلاصه مکالمات قبلی)
        if conversation_id:
            long_term = await self.get_long_term_memory(db, user_id, conversation_id)
            if long_term:
                context.append({
                    "role": "system",
                    "content": f"خلاصه مکالمات قبلی با این کاربر:\n{long_term}"
                })
        
        # 2. حافظه کوتاه‌مدت (پیام‌های اخیر)
        if conversation_id:
            short_term = await self.get_short_term_memory(db, conversation_id)
            context.extend(short_term)
        
        # 3. تحلیل فایل (اگر وجود دارد)
        if file_analysis:
            context.append({
                "role": "system",
                "content": f"تحلیل فایل ضمیمه شده توسط کاربر:\n{file_analysis}"
            })
        
        # 4. سوال فعلی
        context.append({
            "role": "user",
            "content": current_query
        })
        
        logger.info(
            "Context built for LLM",
            user_id=user_id,
            conversation_id=conversation_id,
            context_messages=len(context),
            has_file_analysis=bool(file_analysis)
        )
        
        return context


# Singleton instance
_conversation_memory = None


def get_conversation_memory() -> ConversationMemory:
    """Get conversation memory service instance"""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory
