"""
LLM-based Query Classifier

این ماژول مسئول دسته‌بندی سوالات کاربر است:
- احوالپرسی، چرت‌وپرت، فحش → پاسخ مستقیم
- سوال واقعی → ادامه به RAG Pipeline
"""

import json
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.llm.base import LLMConfig, LLMProvider, Message
from app.llm.openai_provider import OpenAIProvider
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


class QueryCategory(BaseModel):
    """دسته‌بندی سوال"""
    category: str  # "greeting", "chitchat", "invalid", "unclear", "business_question"
    confidence: float  # 0.0 to 1.0
    direct_response: Optional[str] = None  # پاسخ مستقیم (برای همه دسته‌ها)
    reason: Optional[str] = None  # دلیل دسته‌بندی
    needs_rag: bool = True  # آیا نیاز به RAG دارد؟


class QueryClassifier:
    """دسته‌بندی کننده سوالات با LLM"""
    
    def __init__(self):
        """Initialize classifier with dedicated LLM"""
        # استفاده از LLM جداگانه برای classification
        self.llm_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_classification_model or settings.llm_model,
            api_key=settings.llm_classification_api_key or settings.llm_api_key,
            base_url=settings.llm_classification_base_url or settings.llm_base_url,
            temperature=settings.llm_classification_temperature or 0.2,
            max_tokens=settings.llm_classification_max_tokens or 512,
        )
        self.llm = OpenAIProvider(self.llm_config)
        logger.info(f"QueryClassifier initialized with model: {self.llm_config.model}")
    
    async def classify(
        self,
        query: str,
        language: str = "fa",
        context: Optional[str] = None,
        file_analysis: Optional[str] = None
    ) -> QueryCategory:
        """
        دسته‌بندی سوال کاربر با در نظر گرفتن context و فایل‌ها
        
        Args:
            query: متن سوال کاربر
            language: زبان سوال (fa یا en)
            context: خلاصه مکالمات قبلی
            file_analysis: تحلیل فایل‌های ضمیمه
        
        Returns:
            QueryCategory با دسته، اطمینان، و پاسخ مستقیم (در صورت نیاز)
        """
        try:
            # ساخت prompt برای دسته‌بندی
            system_prompt = self._build_classification_prompt(language)
            
            # ساخت پیام کاربر با context و file_analysis (محدود شده)
            user_message_parts = []
            
            # Context را محدود می‌کنیم تا گمراه‌کننده نباشد
            if context:
                context_preview = context[:500] + "..." if len(context) > 500 else context
                user_message_parts.append(f"[Context مکالمه قبلی: {context_preview}]\n")
            
            # File analysis را خلاصه می‌کنیم
            if file_analysis:
                file_preview = file_analysis[:300] + "..." if len(file_analysis) > 300 else file_analysis
                user_message_parts.append(f"[فایل ضمیمه: {file_preview}]\n")
            
            user_message_parts.append(f"سوال کاربر: {query}")
            user_message = "\n".join(user_message_parts)
            
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            # فراخوانی LLM با timeout (5 ثانیه)
            response = await asyncio.wait_for(
                self.llm.generate(messages),
                timeout=5.0
            )
            
            # پارس کردن پاسخ JSON
            result = self._parse_classification_response(response.content)
            
            logger.info(
                f"Query classified: category={result.category}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning("Classification timeout (5s), defaulting to business question")
            return QueryCategory(
                category="business_question",
                confidence=0.5,
                reason="Classification timeout, defaulting to business question"
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # در صورت خطا، فرض می‌کنیم سوال واقعی است
            return QueryCategory(
                category="business_question",
                confidence=0.5,
                reason=f"Classification failed: {str(e)}"
            )
    
    def _build_classification_prompt(self, language: str) -> str:
        """ساخت prompt برای دسته‌بندی"""
        if language == "fa":
            return """شما یک دسته‌بندی کننده هوشمند و پاسخ‌دهنده سریع هستید.

وظیفه شما: سوال کاربر را دسته‌بندی کنید و در صورت امکان پاسخ سریع بدهید.

**دسته‌بندی‌ها:**

1. **greeting** - احوالپرسی
   مثال: "سلام", "درود", "چطوری"
   → پاسخ مستقیم بده، RAG لازم نیست

2. **chitchat** - گفتگوی عمومی
   مثال: "هوا چطوره", "چه خبر"
   → پاسخ مستقیم بده، RAG لازم نیست

3. **invalid** - نامعتبر یا فحش
   مثال: فحش، spam، کاراکترهای تصادفی
   → پاسخ مستقیم بده، RAG لازم نیست

4. **unclear** - سوال مبهم یا ناقص
   مثال: "بررسی کن", "چی؟", "این چیه"
   → از کاربر توضیح بخواه، RAG لازم نیست

5. **business_question** - سوال واقعی کسب‌وکار/حقوقی
   مثال: "قانون کار چیست", "مالیات چقدر است"
   → اگر می‌توانی پاسخ کوتاه بده، وگرنه به RAG بفرست

**قوانین مهم:**
- برای greeting, chitchat, invalid, unclear: حتماً پاسخ مستقیم بده و needs_rag=false
- برای business_question: اگر سوال ساده است، پاسخ کوتاه بده و needs_rag=false
- برای business_question پیچیده: پاسخ نده و needs_rag=true
- اگر فایل ضمیمه شده، احتمالاً business_question است
- سوالات مبهم مثل "بررسی کن" بدون context → unclear

**خروجی JSON:**
{
  "category": "greeting|chitchat|invalid|unclear|business_question",
  "confidence": 0.0-1.0,
  "direct_response": "پاسخ (همیشه پر کن)",
  "needs_rag": true|false,
  "reason": "دلیل"
}

**مثال‌ها:**

1. سلام
{"category": "greeting", "confidence": 0.95, "direct_response": "سلام! چطور می‌توانم کمکتان کنم؟", "needs_rag": false, "reason": "احوالپرسی"}

2. بررسی کن
{"category": "unclear", "confidence": 0.90, "direct_response": "لطفاً مشخص کنید چه چیزی را بررسی کنم؟ می‌توانید سوال خود را واضح‌تر بپرسید.", "needs_rag": false, "reason": "سوال مبهم بدون context"}

3. قانون کار چیست؟
{"category": "business_question", "confidence": 0.95, "direct_response": "قانون کار مجموعه قوانینی است که روابط کارگر و کارفرما را تنظیم می‌کند. برای اطلاعات دقیق‌تر، اجازه دهید در پایگاه داده جستجو کنم.", "needs_rag": true, "reason": "سوال پیچیده نیاز به RAG"}

4. ماده 10 قانون کار چیست؟
{"category": "business_question", "confidence": 0.98, "direct_response": null, "needs_rag": true, "reason": "سوال خاص نیاز به جستجو در پایگاه"}

5. [فایل ضمیمه] + "بررسی کن"
{"category": "business_question", "confidence": 0.85, "direct_response": "فایل شما را دریافت کردم. اجازه دهید آن را تحلیل کنم.", "needs_rag": true, "reason": "درخواست تحلیل فایل"}

فقط JSON برگردان، هیچ توضیح اضافی نده."""

        else:  # English
            return """You are an intelligent query classifier.

Your task: Receive user text and classify it into one of these categories:

1. **greeting** - Greetings and salutations
   Example: "hello", "hi", "how are you", "good morning"

2. **chitchat** - General conversation unrelated to business
   Example: "how's the weather", "do you like football", "what's up"

3. **invalid** - Invalid content, profanity, or nonsense
   Example: profanity, random characters, spam

4. **business_question** - Real question about business, law, rights, tax, contracts, etc.
   Example: "what does labor law say", "how much is income tax", "what is a work contract"

Important rules:
- If question is about business, legal, financial, contractual, tax topics → business_question
- Only provide direct_response for greeting, chitchat, invalid
- For business_question, don't provide direct response, just classify

Return JSON output:
{
  "category": "greeting|chitchat|invalid|business_question",
  "confidence": 0.0-1.0,
  "direct_response": "Direct response (only for non-business_question)",
  "reason": "Classification reason"
}

Only return JSON, no additional explanation."""
    
    def _parse_classification_response(self, response: str) -> QueryCategory:
        """پارس کردن پاسخ JSON از LLM"""
        try:
            # حذف markdown code blocks اگر وجود داشت
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # پارس JSON
            data = json.loads(response)
            
            return QueryCategory(
                category=data.get("category", "business_question"),
                confidence=float(data.get("confidence", 0.5)),
                direct_response=data.get("direct_response"),
                reason=data.get("reason"),
                needs_rag=data.get("needs_rag", True)
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            logger.debug(f"Response was: {response}")
            
            # fallback: تشخیص دستی
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["greeting", "سلام", "احوالپرسی"]):
                return QueryCategory(
                    category="greeting",
                    confidence=0.7,
                    direct_response="سلام! چطور می‌توانم کمک کنم؟",
                    reason="Detected as greeting from response",
                    needs_rag=False
                )
            
            # پیش‌فرض: سوال کسب و کار
            return QueryCategory(
                category="business_question",
                confidence=0.5,
                reason="Failed to parse, defaulting to business question",
                needs_rag=True
            )
