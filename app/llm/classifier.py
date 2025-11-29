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
    category: str  # "greeting", "chitchat", "invalid", "business_question"
    confidence: float  # 0.0 to 1.0
    direct_response: Optional[str] = None  # پاسخ مستقیم برای موارد غیر سوالی
    reason: Optional[str] = None  # دلیل دسته‌بندی


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
    
    async def classify(self, query: str, language: str = "fa") -> QueryCategory:
        """
        دسته‌بندی سوال کاربر
        
        Args:
            query: متن سوال کاربر
            language: زبان سوال (fa یا en)
        
        Returns:
            QueryCategory با دسته، اطمینان، و پاسخ مستقیم (در صورت نیاز)
        """
        try:
            # ساخت prompt برای دسته‌بندی
            system_prompt = self._build_classification_prompt(language)
            user_message = f"متن کاربر: {query}"
            
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
            return """شما یک دسته‌بندی کننده هوشمند سوالات هستید.

وظیفه شما: متن کاربر را دریافت کرده و آن را در یکی از دسته‌های زیر قرار دهید:

1. **greeting** - احوالپرسی و سلام و علیک
   مثال: "سلام", "درود", "چطوری", "خوبی", "صبح بخیر"

2. **chitchat** - گفتگوی عمومی و نامرتبط با کسب و کار
   مثال: "هوا چطوره", "فوتبال دوست داری", "چه خبر"

3. **invalid** - محتوای نامعتبر، فحش، یا بی‌معنی
   مثال: فحش، کاراکترهای تصادفی، spam

4. **business_question** - سوال واقعی درباره کسب و کار، قانون، حقوق، مالیات، قرارداد، و ...
   مثال: "قانون کار چه می‌گوید", "مالیات بر درآمد چقدر است", "قرارداد کار چیست"

قوانین مهم:
- اگر سوال درباره موضوعات کسب و کار، حقوقی، مالی، قراردادی، مالیاتی باشد → business_question
- فقط برای greeting, chitchat, invalid پاسخ مستقیم بده
- برای business_question پاسخ مستقیم نده، فقط دسته‌بندی کن

خروجی را به صورت JSON برگردان:
{
  "category": "greeting|chitchat|invalid|business_question",
  "confidence": 0.0-1.0,
  "direct_response": "پاسخ مستقیم (فقط برای غیر business_question)",
  "reason": "دلیل دسته‌بندی"
}

مثال 1:
ورودی: "سلام"
خروجی: {"category": "greeting", "confidence": 0.95, "direct_response": "سلام! چطور می‌توانم کمک کنم؟", "reason": "احوالپرسی ساده"}

مثال 2:
ورودی: "قانون کار در مورد اخراج چه می‌گوید؟"
خروجی: {"category": "business_question", "confidence": 0.98, "direct_response": null, "reason": "سوال حقوقی درباره قانون کار"}

مثال 3:
ورودی: "asdfghjkl"
خروجی: {"category": "invalid", "confidence": 0.90, "direct_response": "متاسفانه متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح بپرسید.", "reason": "کاراکترهای بی‌معنی"}

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
                reason=data.get("reason")
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
                    reason="Detected as greeting from response"
                )
            
            # پیش‌فرض: سوال کسب و کار
            return QueryCategory(
                category="business_question",
                confidence=0.5,
                reason="Failed to parse, defaulting to business question"
            )
