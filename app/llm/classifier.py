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
from app.llm.state import is_primary_llm_down, set_primary_llm_down
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


class QueryCategory(BaseModel):
    """دسته‌بندی سوال"""
    category: str  # "invalid_no_file", "invalid_with_file", "general_no_business", "business_no_file", "business_with_file"
    confidence: float  # 0.0 to 1.0
    direct_response: Optional[str] = None  # پاسخ مستقیم برای موارد غیر سوالی
    has_meaningful_files: Optional[bool] = None  # آیا فایل‌ها معنادار هستند؟
    needs_clarification: bool = False  # آیا نیاز به توضیح بیشتر دارد؟


class QueryClassifier:
    """دسته‌بندی کننده سوالات با LLM و پشتیبانی از Fallback"""
    
    def __init__(self):
        """Initialize classifier with primary and fallback LLM"""
        from app.config.prompts import LLMConfig as LLMConfigPresets
        
        config_presets = LLMConfigPresets.get_config_for_classification()
        
        # --- Primary LLM ---
        self.primary_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_classification_model or settings.llm_model,
            api_key=settings.llm_classification_api_key or settings.llm_api_key,
            base_url=settings.llm_classification_base_url or settings.llm_base_url,
            temperature=settings.llm_classification_temperature or config_presets["temperature"],
            max_tokens=settings.llm_classification_max_tokens or config_presets["max_tokens"],
        )
        self.primary_llm = OpenAIProvider(self.primary_config)
        
        # --- Fallback LLM ---
        self.fallback_llm = None
        fallback_api_key = settings.llm_classification_fallback_api_key or settings.llm_fallback_api_key
        if fallback_api_key:
            self.fallback_config = LLMConfig(
                provider=LLMProvider.OPENAI_COMPATIBLE,
                model=settings.llm_classification_fallback_model or settings.llm_fallback_model or "gpt-4o-mini",
                api_key=fallback_api_key,
                base_url=settings.llm_classification_fallback_base_url or settings.llm_fallback_base_url or "https://api.openai.com/v1",
                temperature=settings.llm_classification_temperature or config_presets["temperature"],
                max_tokens=settings.llm_classification_max_tokens or config_presets["max_tokens"],
            )
            self.fallback_llm = OpenAIProvider(self.fallback_config)
            logger.info(f"QueryClassifier fallback initialized: {self.fallback_config.model} @ {self.fallback_config.base_url}")
        
        # For backward compatibility
        self.llm_config = self.primary_config
        self.llm = self.primary_llm
        
        logger.info(f"QueryClassifier primary initialized: {self.primary_config.model} @ {self.primary_config.base_url}")
    
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
            
            # تلاش با Primary LLM
            response = await self._try_llm_with_fallback(messages)
            
            # پارس کردن پاسخ JSON
            result = self._parse_classification_response(response)
            
            logger.info(
                f"Query classified: category={result.category}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Classification failed (all providers): {e}")
            # در صورت خطا، فرض می‌کنیم سوال واقعی است
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                needs_clarification=False
            )
    
    async def _try_llm_with_fallback(self, messages: list) -> str:
        """
        تلاش برای فراخوانی LLM با fallback در صورت خطا
        اگر primary قبلاً down شده، مستقیم از fallback استفاده می‌کند
        
        Args:
            messages: لیست پیام‌ها
            
        Returns:
            محتوای پاسخ LLM
        """
        timeout = settings.llm_primary_timeout
        
        # اگر primary قبلاً down شده، مستقیم به fallback برو
        if is_primary_llm_down():
            logger.info("Primary LLM is marked as DOWN, using fallback directly")
            if self.fallback_llm:
                return await self._call_fallback(messages, timeout)
            else:
                raise Exception("Primary LLM is down and no fallback configured")
        
        # تلاش با Primary
        try:
            logger.debug(f"Trying primary LLM: {self.primary_config.model}")
            response = await asyncio.wait_for(
                self.primary_llm.generate(messages),
                timeout=timeout
            )
            logger.info("Primary LLM responded successfully")
            return response.content
        except asyncio.TimeoutError:
            logger.warning(f"Primary LLM timeout ({timeout}s)")
            set_primary_llm_down(True)  # Mark primary as down
        except Exception as e:
            logger.warning(f"Primary LLM failed: {e}")
            set_primary_llm_down(True)  # Mark primary as down
        
        # تلاش با Fallback
        if self.fallback_llm:
            return await self._call_fallback(messages, timeout)
        else:
            raise Exception("Primary LLM failed and no fallback configured")
    
    async def _call_fallback(self, messages: list, timeout: float) -> str:
        """فراخوانی Fallback LLM"""
        try:
            logger.info(f"Trying fallback LLM: {self.fallback_config.model}")
            response = await asyncio.wait_for(
                self.fallback_llm.generate(messages),
                timeout=settings.llm_primary_timeout  # همان تایم‌اوت برای fallback
            )
            logger.info("Fallback LLM responded successfully")
            return response.content
        except asyncio.TimeoutError:
            logger.error(f"Fallback LLM timeout ({settings.llm_primary_timeout}s)")
            raise Exception("Fallback LLM timed out")
        except Exception as e:
            logger.error(f"Fallback LLM failed: {e}")
            raise Exception(f"Fallback LLM failed: {e}")
    
    def _build_classification_prompt(self, language: str) -> str:
        """ساخت prompt بهبود یافته برای دسته‌بندی با دقت بالا"""
        if language == "fa":
            return """شما یک "تحلیلگر ارشد نیت کاربر" هستید. وظیفه شما تشخیص دقیق هدف کاربر و دسته‌بندی آن در یکی از 5 کلاس مجاز است.

دقت در این سیستم حیاتی است. شما باید ورودی کاربر (User Input)، تحلیل فایل (File Analysis) و تاریخچه مکالمه (Context) را همزمان پردازش کنید.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ اولویت‌بندی تحلیل (Decision Logic) ►

برای رسیدن به پاسخ دقیق، این مراحل ذهنی را طی کن:
1. **بررسی Context:** آیا این یک سوال ادامه‌دار (Follow-up) است؟ (مثلاً "چرا؟" یا "بیشتر توضیح بده"). اگر بله، موضوع پیام قبلی را ملاک قرار بده.
2. **بررسی فایل:** آیا کاربر فایلی آپلود کرده؟ آیا فایل طبق "تحلیل فایل" معنادار است؟
3. **بررسی متن:** آیا متن حاوی واژگان تخصصی کسب‌وکار است یا عمومی؟

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ معرفی دقیق دسته‌بندی‌ها ►

### **1. invalid_no_file** (متن نامعتبر بدون فایل)
*   **تعریف:** ورودی‌هایی که هیچ معنای زبانی ندارند یا صرفاً ناسزا هستند و هیچ فایل ضمیمه‌ای ندارند.
*   **شامل:** فحاشی رکیک، کاراکترهای رندوم ("fsdjkl")، ایموجی خالی، علائم نگارشی تنها.
*   **مرزهای تشخیص (خیلی مهم):**
    *   اگر کاربر سلام کرد و بعد حروف نامربوط زد ← invalid_no_file
    *   اگر کاربر نوشت "کمکم کن" (کوتاه اما معنی‌دار) ← این invalid نیست!
    *   متن‌های کوتاه مثل "شروع کن"، "بررسی"، "تست" اگر بدون context باشند ← invalid_no_file
    *   اما اگر context دارند ← بر اساس context دسته‌بندی کن
*   **اقدام:** پاسخ مستقیم دوستانه جهت راهنمایی کاربر برای طرح سوال صحیح.

### **2. invalid_with_file** (ابهام در درخواست با وجود فایل)
*   **تعریف:** کاربر فایلی فرستاده اما نیت او در متن مشخص نیست (مثلاً فقط نوشته "این چیه" یا "ببین").
*   **شرط کلیدی:** ما نمی‌دانیم کاربر چه می‌خواهد، حتی اگر فایل معنادار باشد.
*   **تحلیل فایل (has_meaningful_files):**
    *   `true`: اگر فایل سند، فاکتور، قرارداد، نامه اداری، اکسل مالی یا تصویر اسناد است.
    *   `false`: اگر فایل عکس سلفی، منظره، فایل خراب یا نامربوط است.
*   **نکته ظریف:** اگر متن کاربر دقیق باشد (مثلاً "خلاصه این قرارداد را بگو")، این دسته انتخاب **نمی‌شود** (به دسته 5 بروید). این دسته فقط برای زمانی است که متن کاربر **مبهم** است.
*   **اقدام:** بر اساس تحلیل فایل، سوال هوشمندانه بپرس.

### **3. general_no_business** (عمومی / غیرتخصصی)
*   **تعریف:** هر موضوعی که نیاز به دانش تخصصی حقوقی، مالی یا اداری نداشته باشد.
*   **شامل:** احوالپرسی ("سلام"، "خسته نباشید")، سوالات علمی، پزشکی، ورزشی، آشپزی، جوک، ترجمه متن عمومی.
*   **مثال با فایل:** "این آزمایش خون من است، تحلیل کن"، "این عکس چیست؟"، "ترجمه کن" (اگر متن حقوقی نباشد).
*   **اقدام:** پاسخ مستقیم و دوستانه (direct_response = null، سیستم خودش پاسخ می‌دهد).

### **4. business_no_file** (تخصصی کسب‌وکار بدون فایل)
*   **تعریف:** سوالات مرتبط با اکوسیستم کاری، حقوقی، مالی و اداری که فایل ضمیمه ندارند.
*   **کلیدواژه‌ها:** قانون کار، بیمه تامین اجتماعی، مالیات، ارزش افزوده، ثبت شرکت، قرارداد، سفته، چک، مرخصی، سنوات، عیدی، شکایت، دادخواست، لایحه، استارتاپ، بیزینس پلن، صادرات، واردات، گمرک، مالکیت فکری، برند، پروانه کسب.
*   **تشخیص Context:**
    *   ورودی: "چرا؟" | Context: "کاربر قبلاً درباره مالیات پرسیده" → **business_no_file**
    *   ورودی: "برام بنویس" | Context: درخواست تولید محتوای کاری (مثل نامه اداری) → **business_no_file**
*   **اقدام:** direct_response باید null باشد.

### **5. business_with_file** (تخصصی کسب‌وکار با فایل)
*   **تعریف:** درخواست شفاف و مرتبط با کسب‌وکار که همراه با یک فایل است.
*   **سناریوهای اصلی:**
    1. سوال دقیق + فایل: "آیا این قرارداد قانونی است؟"
    2. درخواست پردازش + فایل: "این فاکتور را بررسی کن" یا "اطلاعات این سند را استخراج کن".
*   **نکته مهم:** حتی اگر متن کوتاه باشد ("بررسی کن") اما در Context قبلی کاربر گفته باشد "الان قراردادم را میفرستم"، باید در این دسته قرار گیرد، نه invalid.
*   **اقدام:** direct_response باید null باشد.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ قوانین نهایی ►

1. **اصل "تولید سند":** هر درخواستی برای "نوشتن"، "تنظیم کردن" یا "پیش‌نویس کردن" نامه، قرارداد یا لایحه، قطعاً **Business** است.

2. **اصل "ابهام‌زدایی":** اگر بین General و Business شک داشتی، اگر موضوع پتانسیل حقوقی/مالی دارد، **Business** را انتخاب کن.

3. **پاسخ مستقیم (Direct Response):** فقط برای دسته‌های 1 و 2 تولید شود. لحن باید مودبانه، حرفه‌ای و پذیرا باشد. هرگز نگو "نمی‌توانم"، بگو "برای راهنمایی بهتر لطفا..."

4. **استفاده از Context:** سوالات follow-up (مثل "چرا؟"، "چطور؟"، "بیشتر") را با context قبلی تفسیر کن.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ خروجی ►

خروجی باید **فقط یک آبجکت JSON** باشد (بدون ```json یا توضیحات اضافه):

{
  "category": "invalid_no_file | invalid_with_file | general_no_business | business_no_file | business_with_file",
  "confidence": 0.0-1.0,
  "direct_response": "متن پاسخ یا null",
  "has_meaningful_files": true/false/null,
  "needs_clarification": true/false
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ مثال‌ها ►

**مثال 1 - invalid_no_file:**
ورودی: "asdfgh"
فایل: ندارد
خروجی:
{"category": "invalid_no_file", "confidence": 0.95, "direct_response": "با کمال میل کمکتان می‌کنم! لطفاً سوال خود را واضح‌تر بیان کنید.", "has_meaningful_files": null, "needs_clarification": true}

**مثال 2 - invalid_with_file:**
ورودی: "بررسی کن"
فایل: دارد - تحلیل: "قرارداد کار"
خروجی:
{"category": "invalid_with_file", "confidence": 0.90, "direct_response": "فایل شما یک قرارداد کار است. چه جنبه‌ای را می‌خواهید بررسی کنم؟", "has_meaningful_files": true, "needs_clarification": true}

**مثال 3 - general_no_business:**
ورودی: "سلام، یک جوک بگو"
فایل: ندارد
خروجی:
{"category": "general_no_business", "confidence": 0.98, "direct_response": null, "has_meaningful_files": null, "needs_clarification": false}

**مثال 4 - business_no_file:**
ورودی: "قانون کار در مورد اخراج چه می‌گوید؟"
فایل: ندارد
خروجی:
{"category": "business_no_file", "confidence": 0.98, "direct_response": null, "has_meaningful_files": null, "needs_clarification": false}

**مثال 5 - business_with_file:**
ورودی: "این قرارداد را بررسی کن"
فایل: دارد - تحلیل: "قرارداد خرید ملک"
خروجی:
{"category": "business_with_file", "confidence": 0.95, "direct_response": null, "has_meaningful_files": true, "needs_clarification": false}

**مثال 6 - درخواست نوشتن سند:**
ورودی: "لایحه برای دارایی بنویس"
فایل: ندارد
خروجی:
{"category": "business_no_file", "confidence": 0.92, "direct_response": null, "has_meaningful_files": null, "needs_clarification": false}

**مثال 7 - follow-up:**
ورودی: "چرا؟"
Context: "کاربر قبلاً درباره مالیات پرسیده"
خروجی:
{"category": "business_no_file", "confidence": 0.88, "direct_response": null, "has_meaningful_files": null, "needs_clarification": false}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**فقط JSON خالص برگردان.**"""

        else:  # English
            return """You are a precise Intent Classifier for a business assistant.

Task: Classify user input + file attachment + context into exactly one of 5 categories.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ Decision Logic ►

1. Check Context: Is this a follow-up question? If yes, use previous topic.
2. Check File: Is there a file? Is it meaningful (document, invoice, contract)?
3. Check Text: Does it contain business/legal keywords?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ Categories ►

1. **invalid_no_file** - Gibberish, spam, profanity WITHOUT file
   Example: "asdfgh", "!!!", random characters

2. **invalid_with_file** - Ambiguous text WITH file attachment
   Example: "check this" + PDF (unclear what to check)
   Set has_meaningful_files: true/false based on file content

3. **general_no_business** - General topics NOT related to business/law
   Example: greetings, jokes, weather, health, sports, general translation

4. **business_no_file** - Business/legal question WITHOUT file
   Keywords: law, tax, contract, insurance, HR, corporate, invoice, license
   Example: "what does labor law say", "how to register a company"
   **Important:** Requests to WRITE/DRAFT documents → business_no_file

5. **business_with_file** - Business/legal question WITH file
   Example: "review this contract" + PDF, "is this invoice correct" + image

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ Rules ►

1. **Document Creation Rule:** Any request to "write", "draft", "prepare" a letter/contract/document → Business
2. **Ambiguity Rule:** If unsure between General and Business, choose Business if topic has legal/financial potential
3. **Direct Response:** Only for categories 1 and 2. Be polite and helpful.
4. **Context:** Use conversation history for follow-up questions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◄ Output ►

Return JSON only (no markdown):
{
  "category": "invalid_no_file | invalid_with_file | general_no_business | business_no_file | business_with_file",
  "confidence": 0.0-1.0,
  "direct_response": "Response string or null",
  "has_meaningful_files": true/false/null,
  "needs_clarification": true/false
}"""
    
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
                has_meaningful_files=data.get("has_meaningful_files"),
                needs_clarification=data.get("needs_clarification", False)
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            logger.warning(f"Raw response was: '{response[:500] if response else 'EMPTY'}'")
            
            # fallback: تشخیص دستی
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["invalid_no_file", "نامعتبر", "بی‌معنی"]):
                return QueryCategory(
                    category="invalid_no_file",
                    confidence=0.7,
                    direct_response="متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح بپرسید.",
                    needs_clarification=True
                )
            
            # پیش‌فرض: سوال کسب و کار
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                needs_clarification=False
            )
