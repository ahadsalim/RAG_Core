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
    category: str  # "invalid_no_file", "invalid_with_file", "general_no_business", "business_no_file", "business_with_file"
    confidence: float  # 0.0 to 1.0
    direct_response: Optional[str] = None  # پاسخ مستقیم برای موارد غیر سوالی
    reason: Optional[str] = None  # دلیل دسته‌بندی
    has_meaningful_files: Optional[bool] = None  # آیا فایل‌ها معنادار هستند؟
    needs_clarification: bool = False  # آیا نیاز به توضیح بیشتر دارد؟


class QueryClassifier:
    """دسته‌بندی کننده سوالات با LLM"""
    
    def __init__(self):
        """Initialize classifier with dedicated LLM"""
        from app.config.prompts import LLMConfig as LLMConfigPresets
        
        # استفاده از LLM جداگانه برای classification
        config_presets = LLMConfigPresets.get_config_for_classification()
        
        self.llm_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_classification_model or settings.llm_model,
            api_key=settings.llm_classification_api_key or settings.llm_api_key,
            base_url=settings.llm_classification_base_url or settings.llm_base_url,
            temperature=settings.llm_classification_temperature or config_presets["temperature"],
            max_tokens=settings.llm_classification_max_tokens or config_presets["max_tokens"],
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
            
            # ساخت پیام کاربر با context و file_analysis
            user_message_parts = []
            
            if context:
                user_message_parts.append(f"خلاصه مکالمات قبلی:\n{context}\n")
            
            if file_analysis:
                user_message_parts.append(f"تحلیل فایل‌های ضمیمه:\n{file_analysis}\n")
            
            user_message_parts.append(f"سوال فعلی کاربر: {query}")
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
            logger.warning("Classification timeout (5s), defaulting to business_no_file")
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                reason="Classification timeout, defaulting to business_no_file",
                needs_clarification=False
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # در صورت خطا، فرض می‌کنیم سوال واقعی است
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                reason=f"Classification failed: {str(e)}",
                needs_clarification=False
            )
    
    def _build_classification_prompt(self, language: str) -> str:
        """ساخت prompt برای دسته‌بندی"""
        if language == "fa":
            return """شما یک دسته‌بندی کننده هوشمند و دقیق سوالات کاربران هستید.

**وظیفه:** متن کاربر و فایل‌های ضمیمه (در صورت وجود) را دریافت کرده و با دقت بالا در یکی از 5 دسته زیر قرار دهید:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. invalid_no_file** - متن نامعتبر/مبهم/بی‌معنی بدون فایل
   شامل: فحش، کاراکترهای تصادفی، جملات بی‌معنی، spam
   مثال: "asdfgh", "!!!", "@#$%"
   
   **توجه مهم:** اگر متن حتی کمی قابل فهم است، آن را invalid ندانید!
   - "بررسی کن" با context → business
   - "چیه این" با context → business  
   - سوالات follow-up → business
   
   **اقدام:** پاسخ دوستانه و کمک‌کننده بده
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**2. invalid_with_file** - متن نامعتبر/مبهم اما با فایل
   شامل: متن مبهم + فایل ضمیمه
   مثال: "بررسی کن" + فایل PDF، "چی میگه" + عکس
   
   **تحلیل فایل:**
   - اگر فایل معنادار است (سند، قرارداد، فاکتور، تصویر مفید) → has_meaningful_files: true
   - اگر فایل بی‌معنی است (عکس تصادفی، فایل خراب) → has_meaningful_files: false
   
   **اقدام:**
   - فایل معنادار: به عنوان مشاور، بر اساس تحلیل فایل سوال هوشمندانه بپرس
   - فایل بی‌معنی: از کاربر توضیح واضح بخواه
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**3. general_no_business** - سوال مفهوم اما نامرتبط با کسب و کار
   شامل: احوالپرسی، سوالات عمومی، جوک، پزشکی، ورزشی، سرگرمی، ...
   مثال: "سلام چطوری", "هوا چطوره", "یک جوک بگو", "سردرد دارم چیکار کنم"
   
   **اقدام:** به صورت عمومی پاسخ بده (بدون استفاده از RAG)
   توجه: اگر فایل دارد، فایل را هم در نظر بگیر
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**4. business_no_file** - سوال مفهوم درباره کسب و کار بدون فایل
   شامل: قانون، حقوق، مالیات، قرارداد، تجارت، شرکت، بیمه، کار، لایحه، پیش‌نویس، ...
   مثال: 
   - "قانون کار چه می‌گوید؟"
   - "مالیات بر ارزش افزوده چیست؟"
   - "نحوه ثبت شرکت؟"
   - "می‌تونی لایحه برای دارایی بنویسی؟" ← business است!
   - "چرا نمی‌تونی؟" (با context قبلی) ← business است!
   
   **اقدام:** سوال را normalize کن و به RAG Pipeline بفرست
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**5. business_with_file** - سوال مفهوم درباره کسب و کار با فایل
   شامل: سوال کسب و کار + فایل (سند، قرارداد، فاکتور، تصویر اسناد، ...)
   مثال: "این قرارداد را بررسی کن" + PDF، "این فاکتور درست است؟" + عکس
   
   **اقدام:** 
   1. تحلیل فایل
   2. سوال را normalize کن
   3. جستجو در RAG
   4. ترکیب نتایج RAG + تحلیل فایل
   5. تولید پاسخ جامع
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**قوانین مهم:**

1. **تشخیص کسب و کار (بسیار مهم!):**
   موضوعات کسب و کار شامل: قانون، حقوق، مالیات، قرارداد، تجارت، شرکت، بیمه، کار، استخدام، اخراج، حقوق و دستمزد، بازرگانی، صادرات، واردات، گمرک، ثبت شرکت، مالکیت فکری، ثبت اختراع، برند، لیسانس، مجوز، پروانه کسب، **لایحه، پیش‌نویس، نوشتن سند، تهیه قرارداد**، و هر موضوع مرتبط با فعالیت‌های اقتصادی و تجاری
   
   **نکته حیاتی:** اگر کاربر از شما می‌خواهد سندی بنویسید (لایحه، قرارداد، پیش‌نویس) → business است!

2. **تشخیص فایل معنادار:**
   - معنادار: PDF اسناد، تصویر قرارداد، فاکتور، فرم، سند رسمی، جدول، نمودار
   - بی‌معنی: عکس تصادفی، فایل خراب، تصویر بی‌ربط

3. **متن مبهم:**
   - "بررسی کن", "چیه این", "بگو", "توضیح بده" بدون context و بدون فایل → مبهم
   - اما اگر فایل معنادار دارد → invalid_with_file با has_meaningful_files: true
   - اگر context قبلی دارد (مثلاً "چرا نمی‌تونی؟") → business است، نه invalid!

4. **پاسخ مستقیم:**
   - فقط برای: invalid_no_file, invalid_with_file (فایل بی‌معنی), general_no_business
   - برای business_no_file و business_with_file: direct_response = null
   
5. **لحن پاسخ‌های مستقیم:**
   - **دوستانه و کمک‌کننده** باشید، نه خشک و ناامیدکننده!
   - به جای: "متأسفانه نمی‌توانم به این سوال پاسخ دهم"
   - بگویید: "با کمال میل کمکتان می‌کنم! لطفاً سوال خود را کمی واضح‌تر بیان کنید تا بهترین پاسخ را بدهم."
   
6. **استفاده از Context:**
   - اگر context مکالمات قبلی دارید، حتماً از آن استفاده کنید
   - سوالات follow-up (مثل "چرا؟", "چطور؟") را با context قبلی تفسیر کنید

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**خروجی JSON:**

{
  "category": "invalid_no_file | invalid_with_file | general_no_business | business_no_file | business_with_file",
  "confidence": 0.0-1.0,
  "direct_response": "پاسخ مستقیم (یا null)",
  "reason": "دلیل دسته‌بندی",
  "has_meaningful_files": true/false/null,
  "needs_clarification": true/false
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**مثال‌ها:**

**مثال 1:**
ورودی: "asdfgh"
فایل: ندارد
خروجی:
{
  "category": "invalid_no_file",
  "confidence": 0.95,
  "direct_response": "با کمال میل کمکتان می‌کنم! لطفاً سوال خود را به صورت واضح‌تر بیان کنید تا بهترین پاسخ را بدهم. 😊",
  "reason": "کاراکترهای بی‌معنی بدون فایل",
  "has_meaningful_files": null,
  "needs_clarification": true
}

**مثال 2:**
ورودی: "بررسی کن"
فایل: دارد - تحلیل فایل: "قرارداد کار بین شرکت الف و آقای احمدی"
خروجی:
{
  "category": "invalid_with_file",
  "confidence": 0.90,
  "direct_response": "فایل شما یک قرارداد کار است. چه جنبه‌ای از این قرارداد را می‌خواهید بررسی کنم؟ آیا سوال خاصی درباره شرایط، حقوق، مدت قرارداد یا سایر بندها دارید؟",
  "reason": "متن مبهم اما فایل معنادار - نیاز به توضیح بیشتر",
  "has_meaningful_files": true,
  "needs_clarification": true
}

**مثال 3:**
ورودی: "سلام، یک جوک بگو"
فایل: ندارد
خروجی:
{
  "category": "general_no_business",
  "confidence": 0.98,
  "direct_response": null,
  "reason": "درخواست جوک - نامرتبط با کسب و کار",
  "has_meaningful_files": null,
  "needs_clarification": false
}

**مثال 4:**
ورودی: "قانون کار در مورد اخراج چه می‌گوید؟"
فایل: ندارد
خروجی:
{
  "category": "business_no_file",
  "confidence": 0.98,
  "direct_response": null,
  "reason": "سوال حقوقی واضح درباره قانون کار",
  "has_meaningful_files": null,
  "needs_clarification": false
}

**مثال 5:**
ورودی: "این قرارداد را بررسی کن و بگو آیا شرایط آن منصفانه است؟"
فایل: دارد - تحلیل فایل: "قرارداد خرید و فروش ملک"
خروجی:
{
  "category": "business_with_file",
  "confidence": 0.95,
  "direct_response": null,
  "reason": "سوال حقوقی واضح با فایل قرارداد",
  "has_meaningful_files": true,
  "needs_clarification": false
}

**مثال 6 (مهم!):**
ورودی: "تو می تونی لایحه برای دارایی بنویسی؟"
فایل: ندارد
Context: ندارد
خروجی:
{
  "category": "business_no_file",
  "confidence": 0.92,
  "direct_response": null,
  "reason": "درخواست نوشتن لایحه - موضوع کسب و کار و حقوقی",
  "has_meaningful_files": null,
  "needs_clarification": false
}

**مثال 7 (follow-up):**
ورودی: "چرا نمی تونی؟"
فایل: ندارد
Context: "کاربر قبلاً پرسیده: تو می تونی لایحه برای دارایی بنویسی؟"
خروجی:
{
  "category": "business_no_file",
  "confidence": 0.88,
  "direct_response": null,
  "reason": "سوال follow-up به سوال قبلی درباره لایحه - موضوع کسب و کار",
  "has_meaningful_files": null,
  "needs_clarification": false
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**فقط JSON خالص برگردان، بدون هیچ توضیح اضافی.**"""

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
                category=data.get("category", "business_no_file"),
                confidence=float(data.get("confidence", 0.5)),
                direct_response=data.get("direct_response"),
                reason=data.get("reason"),
                has_meaningful_files=data.get("has_meaningful_files"),
                needs_clarification=data.get("needs_clarification", False)
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            logger.debug(f"Response was: {response}")
            
            # fallback: تشخیص دستی
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["invalid_no_file", "نامعتبر", "بی‌معنی"]):
                return QueryCategory(
                    category="invalid_no_file",
                    confidence=0.7,
                    direct_response="متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح بپرسید.",
                    reason="Detected as invalid from response",
                    needs_clarification=True
                )
            
            # پیش‌فرض: سوال کسب و کار
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                reason="Failed to parse, defaulting to business_no_file",
                needs_clarification=False
            )
