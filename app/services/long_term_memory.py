"""
Long-Term Memory Service - حافظه بلندمدت کاربر
===============================================
این سرویس مسئول مدیریت حافظه بلندمدت کاربران است.

سه نوع حافظه:
1. حافظه کوتاه‌مدت: 10 پیام آخر (متن کامل)
2. حافظه چت: خلاصه پیام‌های قدیمی + 10 پیام آخر
3. حافظه بلندمدت: اطلاعات پایدار کاربر (مشترک بین همه چت‌ها)
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
import structlog

from app.models.user import UserProfile, Conversation, Message as DBMessage, MessageRole, UserMemory, MemoryCategory
from app.llm.base import LLMConfig, LLMProvider, Message
from app.llm.openai_provider import OpenAIProvider
from app.config.settings import settings

logger = structlog.get_logger()


class LongTermMemoryService:
    """
    سرویس مدیریت حافظه بلندمدت کاربر
    
    این حافظه شامل اطلاعات پایدار کاربر است که در تمام مکالمات استفاده می‌شود.
    """
    
    # تنظیمات
    MAX_MEMORY_ITEMS = 20  # حداکثر تعداد آیتم‌های حافظه
    MIN_MEMORY_ITEMS = 5   # حداقل تعداد آیتم‌ها قبل از خلاصه‌سازی
    
    def __init__(self):
        """Initialize with LLM1 (Light) for memory extraction and summarization."""
        from app.llm.factory import create_llm1_light
        self.llm = create_llm1_light()
        logger.info("LongTermMemoryService initialized with LLM1 (Light)")
    
    # ==================== ماژول 1: تشخیص و استخراج حافظه ====================
    
    async def extract_memory_from_message(
        self,
        user_message: str,
        assistant_response: str,
        conversation_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        تشخیص و استخراج اطلاعات قابل ذخیره از پیام
        
        Returns:
            {
                "should_write_memory": bool,
                "memory_to_write": str,
                "category": str
            }
        """
        from app.config.prompts import MemoryPrompts
        
        system_prompt = MemoryPrompts.get_memory_extraction_prompt()

        user_content = MemoryPrompts.format_memory_extraction_user(
            user_message=user_message,
            assistant_response=assistant_response,
            conversation_context=conversation_context
        )

        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_content)
            ]
            
            # استفاده از Responses API
            response = await self.llm.generate_responses_api(
                messages,
                reasoning_effort="low"
            )
            
            # Parse JSON response
            result = self._parse_json_response(response.content)
            
            logger.info(
                "Memory extraction completed",
                should_write=result.get("should_write_memory", False),
                category=result.get("category", "")
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return {"should_write_memory": False, "memory_to_write": "", "category": ""}
    
    # ==================== ماژول 2: ادغام و بروزرسانی حافظه ====================
    
    async def merge_memory(
        self,
        db: AsyncSession,
        user_id: str,
        new_memory: str,
        category: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ادغام حافظه جدید با حافظه‌های موجود
        
        Returns:
            {
                "action": "added" | "updated" | "skipped",
                "memory_id": str | None
            }
        """
        try:
            # دریافت حافظه‌های موجود
            existing_memories = await self.get_user_memories(db, user_id)
            
            if not existing_memories:
                # اولین حافظه - مستقیم اضافه کن
                memory_id = await self._add_memory(
                    db, user_id, new_memory, category, conversation_id
                )
                return {"action": "added", "memory_id": str(memory_id)}
            
            # بررسی شباهت با LLM
            merge_result = await self._check_similarity_and_merge(
                existing_memories, new_memory, category
            )
            
            if merge_result["should_add"]:
                memory_id = await self._add_memory(
                    db, user_id, new_memory, category, conversation_id
                )
                return {"action": "added", "memory_id": str(memory_id)}
            
            elif merge_result["should_update"]:
                memory_id = merge_result["update_id"]
                await self._update_memory(
                    db, memory_id, merge_result["updated_content"]
                )
                return {"action": "updated", "memory_id": memory_id}
            
            else:
                return {"action": "skipped", "memory_id": None}
                
        except Exception as e:
            logger.error(f"Memory merge failed: {e}")
            return {"action": "error", "memory_id": None}
    
    async def _check_similarity_and_merge(
        self,
        existing_memories: List[Dict],
        new_memory: str,
        category: str
    ) -> Dict[str, Any]:
        """بررسی شباهت و تصمیم‌گیری برای ادغام"""
        
        system_prompt = """تو ماژول ادغام حافظه هستی.

ورودی:
1. لیست حافظه‌های موجود کاربر
2. حافظه جدید پیشنهادی

وظایف:
1. بررسی کن که آیا حافظه جدید با یکی از قبلی‌ها مشابه است؟
2. اگر مشابه است و جدیدتر/دقیق‌تر است → به‌روزرسانی
3. اگر کاملاً جدید است → اضافه کن
4. اگر تکراری/غیرضروری است → رد کن

خروجی فقط JSON:
{
    "should_add": true/false,
    "should_update": true/false,
    "update_index": -1 یا شماره آیتم (0-indexed),
    "updated_content": "محتوای به‌روزشده اگر should_update=true",
    "reason": "توضیح کوتاه"
}"""

        memories_text = "\n".join([
            f"{i}. [{m['category']}] {m['content']}"
            for i, m in enumerate(existing_memories)
        ])
        
        user_content = f"""حافظه‌های موجود:
{memories_text}

حافظه جدید: [{category}] {new_memory}"""

        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_content)
            ]
            
            # استفاده از Responses API
            response = await self.llm.generate_responses_api(
                messages,
                reasoning_effort="low"
            )
            result = self._parse_json_response(response.content)
            
            # Map index to actual memory ID
            if result.get("should_update") and result.get("update_index", -1) >= 0:
                idx = result["update_index"]
                if idx < len(existing_memories):
                    result["update_id"] = existing_memories[idx]["id"]
            
            return result
            
        except Exception as e:
            logger.error(f"Similarity check failed: {e}")
            return {"should_add": True, "should_update": False}
    
    # ==================== ماژول 3: خلاصه‌سازی حافظه ====================
    
    async def summarize_memories(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """
        خلاصه‌سازی و تمیزکاری حافظه‌های کاربر
        
        Returns:
            {
                "success": bool,
                "before_count": int,
                "after_count": int
            }
        """
        try:
            existing_memories = await self.get_user_memories(db, user_id)
            
            if len(existing_memories) <= self.MIN_MEMORY_ITEMS:
                return {
                    "success": True,
                    "before_count": len(existing_memories),
                    "after_count": len(existing_memories),
                    "message": "No summarization needed"
                }
            
            # خلاصه‌سازی با LLM
            clean_memories = await self._summarize_with_llm(existing_memories)
            
            if clean_memories:
                # حذف حافظه‌های قدیمی و اضافه کردن جدید
                await self._replace_memories(db, user_id, clean_memories)
                
                return {
                    "success": True,
                    "before_count": len(existing_memories),
                    "after_count": len(clean_memories)
                }
            
            return {"success": False, "error": "Summarization failed"}
            
        except Exception as e:
            logger.error(f"Memory summarization failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _summarize_with_llm(
        self,
        memories: List[Dict]
    ) -> Optional[List[Dict]]:
        """خلاصه‌سازی حافظه‌ها با LLM"""
        
        system_prompt = """تو ماژول خلاصه‌ساز حافظه هستی.

ورودی: لیست حافظه‌های ذخیره‌شده کاربر

وظیفه:
حافظه‌ها را به شکلی خلاصه، تمیز، بدون تکرار و در قالب 5 تا 15 آیتم معنادار بازنویسی کن.

قوانین:
- محتوا را تغییر نده، فقط ساده‌تر بیان کن
- موارد مشابه را ادغام کن
- موارد قدیمی/بی‌ربط را حذف کن
- دسته‌بندی را حفظ کن

خروجی فقط JSON:
{
    "clean_memories": [
        {"content": "...", "category": "personal_info|preference|goal|interest|context|behavior|other"},
        ...
    ]
}"""

        memories_text = "\n".join([
            f"- [{m['category']}] {m['content']}"
            for m in memories
        ])
        
        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=f"حافظه‌های فعلی:\n{memories_text}")
            ]
            
            # استفاده از Responses API
            response = await self.llm.generate_responses_api(
                messages,
                reasoning_effort="low"
            )
            result = self._parse_json_response(response.content)
            
            return result.get("clean_memories", [])
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return None
    
    # ==================== Database Operations ====================
    
    async def get_user_memories(
        self,
        db: AsyncSession,
        user_id: str,
        active_only: bool = True
    ) -> List[Dict]:
        """دریافت تمام حافظه‌های کاربر"""
        try:
            query = select(UserMemory).filter(UserMemory.user_id == user_id)
            
            if active_only:
                query = query.filter(UserMemory.is_active == True)
            
            query = query.order_by(UserMemory.created_at.desc())
            
            result = await db.execute(query)
            memories = result.scalars().all()
            
            return [
                {
                    "id": str(m.id),
                    "content": m.content,
                    "category": m.category.value,
                    "confidence": m.confidence,
                    "usage_count": m.usage_count,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None
                }
                for m in memories
            ]
            
        except Exception as e:
            logger.error(f"Failed to get user memories: {e}")
            return []
    
    async def get_memory_context(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Optional[str]:
        """
        دریافت context حافظه بلندمدت برای استفاده در query
        
        Returns:
            متن فرمت‌شده حافظه‌ها برای ارسال به LLM
        """
        memories = await self.get_user_memories(db, user_id)
        
        if not memories:
            return None
        
        # فرمت‌بندی برای LLM
        lines = ["اطلاعات پایدار کاربر:"]
        for m in memories:
            lines.append(f"- {m['content']}")
        
        # Update usage count
        await self._increment_usage_counts(db, [m["id"] for m in memories])
        
        return "\n".join(lines)
    
    async def _add_memory(
        self,
        db: AsyncSession,
        user_id: str,
        content: str,
        category: str,
        conversation_id: Optional[str] = None
    ) -> uuid.UUID:
        """اضافه کردن حافظه جدید"""
        try:
            # Map category string to enum
            cat_enum = MemoryCategory(category) if category else MemoryCategory.OTHER
        except ValueError:
            cat_enum = MemoryCategory.OTHER
        
        memory = UserMemory(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            content=content,
            category=cat_enum,
            source_conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(memory)
        await db.commit()
        
        logger.info(
            "Memory added",
            user_id=user_id,
            category=category,
            content_length=len(content)
        )
        
        return memory.id
    
    async def _update_memory(
        self,
        db: AsyncSession,
        memory_id: str,
        new_content: str
    ):
        """به‌روزرسانی حافظه موجود"""
        await db.execute(
            update(UserMemory)
            .where(UserMemory.id == memory_id)
            .values(
                content=new_content,
                version=UserMemory.version + 1,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        logger.info("Memory updated", memory_id=memory_id)
    
    async def _increment_usage_counts(
        self,
        db: AsyncSession,
        memory_ids: List[str]
    ):
        """افزایش شمارنده استفاده"""
        for mid in memory_ids:
            await db.execute(
                update(UserMemory)
                .where(UserMemory.id == mid)
                .values(
                    usage_count=UserMemory.usage_count + 1,
                    last_used_at=datetime.utcnow()
                )
            )
        await db.commit()
    
    async def _replace_memories(
        self,
        db: AsyncSession,
        user_id: str,
        new_memories: List[Dict]
    ):
        """جایگزینی حافظه‌ها با لیست جدید (برای خلاصه‌سازی)"""
        # Soft delete old memories
        await db.execute(
            update(UserMemory)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.is_active == True)
            .values(is_active=False)
        )
        
        # Add new memories
        for m in new_memories:
            await self._add_memory(
                db, user_id, m["content"], m.get("category", "other")
            )
        
        logger.info(
            "Memories replaced",
            user_id=user_id,
            new_count=len(new_memories)
        )
    
    async def delete_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str
    ) -> bool:
        """حذف یک حافظه (soft delete)"""
        result = await db.execute(
            update(UserMemory)
            .where(UserMemory.id == memory_id)
            .where(UserMemory.user_id == user_id)
            .values(is_active=False)
        )
        await db.commit()
        
        return result.rowcount > 0
    
    async def update_memory_content(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
        new_content: str,
        new_category: Optional[str] = None
    ) -> bool:
        """ویرایش محتوای حافظه توسط کاربر"""
        values = {
            "content": new_content,
            "updated_at": datetime.utcnow(),
            "version": UserMemory.version + 1
        }
        
        if new_category:
            try:
                values["category"] = MemoryCategory(new_category)
            except ValueError:
                pass
        
        result = await db.execute(
            update(UserMemory)
            .where(UserMemory.id == memory_id)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.is_active == True)
            .values(**values)
        )
        await db.commit()
        
        return result.rowcount > 0
    
    async def clear_all_memories(
        self,
        db: AsyncSession,
        user_id: str
    ) -> int:
        """پاک کردن تمام حافظه‌های کاربر"""
        result = await db.execute(
            update(UserMemory)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.is_active == True)
            .values(is_active=False)
        )
        await db.commit()
        
        logger.info("All memories cleared", user_id=user_id, count=result.rowcount)
        
        return result.rowcount
    
    # ==================== Helpers ====================
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response"""
        try:
            # Try to extract JSON from response
            content = content.strip()
            
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content)
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response", content=content[:200])
            return {}


# Singleton instance
_long_term_memory_service: Optional[LongTermMemoryService] = None


def get_long_term_memory_service() -> LongTermMemoryService:
    """Get long-term memory service instance"""
    global _long_term_memory_service
    if _long_term_memory_service is None:
        _long_term_memory_service = LongTermMemoryService()
    return _long_term_memory_service
