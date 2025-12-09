#!/usr/bin/env python3
"""
تست کلاسیفیکیشن LLM - نسخه تعاملی
نصب: pip install openai
اجرا: python test_class.py
"""

import json
from openai import OpenAI

# ============================================================================
# تنظیمات LLM
# ============================================================================
API_KEY = "sk-o92MoYgtEGcJrtvYEPS8t3BTWCwUfdg6o3HzdA67L3yWtddO"
BASE_URL = "https://api.gapgpt.app/v1"

# دو مدل برای مقایسه
MODELS = [
    {"name": "gpt-4o-mini", "label": "GPT-4o-mini", "max_tokens": 128},
    {"name": "gpt-5-nano", "label": "GPT-5-nano", "max_tokens": 512},
]

MAX_TOKENS_DEFAULT = 128  # پیش‌فرض برای مدل‌های بدون تنظیم خاص
MAX_TOKENS_RESPONSE = 2048  # برای مرحله دوم (پاسخ‌دهی)
TEMPERATURE = 0.2

# ============================================================================
# پرامپت پاسخ‌دهی عمومی (general) - از کد اصلی
# ============================================================================

GENERAL_PROMPT = """شما یک دستیار هوشمند فارسی‌زبان هستید.
به سوالات عمومی کاربر پاسخ دهید.

قوانین مهم:
1. هرگز نام مدل یا شرکت سازنده خود را فاش نکنید (OpenAI، GPT، Claude و غیره)
2. هرگز به تاریخ آموزش یا محدودیت‌های دانش خود اشاره نکنید
3. خود را "دستیار هوشمند" معرفی کنید
4. پاسخ‌ها باید مختصر، مفید و دوستانه باشند
5. اگر سوال خارج از توانایی شماست، مودبانه بگویید که نمی‌توانید کمک کنید
6. از ذکر جزئیات فنی مانند نام مدل، نسخه، تاریخ آموزش خودداری کنید"""

# ============================================================================
# پرامپت کلاسیفیکیشن (فارسی)
# ============================================================================

CLASSIFICATION_PROMPT_FA = """شما یک "تحلیلگر ارشد نیت کاربر" هستید. وظیفه شما تشخیص دقیق هدف کاربر و دسته‌بندی آن در یکی از 5 کلاس مجاز است.

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

### **3. general** (عمومی / غیرتخصصی)
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
  "category": "invalid_no_file | invalid_with_file | general | business_no_file | business_with_file",
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

**مثال 3 - general:**
ورودی: "سلام، یک جوک بگو"
فایل: ندارد
خروجی:
{"category": "general", "confidence": 0.98, "direct_response": null, "has_meaningful_files": null, "needs_clarification": false}

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


def build_user_message(query: str, file_analysis: str = None) -> str:
    """ساخت پیام کاربر برای ارسال به LLM"""
    parts = []
    parts.append(f"**ورودی کاربر (User Input):**\n{query}")
    
    if file_analysis:
        parts.append(f"\n**تحلیل فایل (File Analysis):**\n{file_analysis}")
    else:
        parts.append("\n**تحلیل فایل (File Analysis):**\nفایلی ارسال نشده است.")
    
    parts.append("\n**تاریخچه مکالمه (Context):**\nاین اولین پیام کاربر است.")
    return "\n".join(parts)


def classify_chat_api(query: str, file_analysis: str, model: str, max_tokens: int) -> dict:
    """کلاسیفیکیشن با Chat Completions API (برای gpt-4o-mini)"""
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    user_message = build_user_message(query, file_analysis)
    
    messages = [
        {"role": "system", "content": CLASSIFICATION_PROMPT_FA},
        {"role": "user", "content": user_message}
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=TEMPERATURE
        )
        
        raw_response = response.choices[0].message.content or ""
        
        # استخراج توکن مصرفی
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'completion_tokens', 0)
        
        result = parse_response(raw_response)
        result['input_tokens'] = input_tokens
        result['output_tokens'] = output_tokens
        return result
            
    except Exception as e:
        return {"error": str(e)}


def classify_responses_api(query: str, file_analysis: str, model: str, max_tokens: int) -> dict:
    """کلاسیفیکیشن با Responses API (برای gpt-5-nano)"""
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    user_message = build_user_message(query, file_analysis)
    
    # ترکیب system prompt و user message
    full_input = f"{CLASSIFICATION_PROMPT_FA}\n\n---\n\n{user_message}"
    
    try:
        response = client.responses.create(
            model=model,
            input=full_input,
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=max_tokens,
        )
        
        # استخراج متن از پاسخ
        raw_response = ""
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                if hasattr(output_item, 'content') and output_item.content:
                    for content_item in output_item.content:
                        if hasattr(content_item, 'text') and content_item.text:
                            raw_response = content_item.text
                            break
                    if raw_response:
                        break
        
        # استخراج توکن مصرفی
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage') and response.usage:
            # Responses API فرمت متفاوت دارد
            input_tokens = getattr(response.usage, 'input_tokens', 0) or getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'output_tokens', 0) or getattr(response.usage, 'completion_tokens', 0)
        
        result = parse_response(raw_response)
        result['input_tokens'] = input_tokens
        result['output_tokens'] = output_tokens
        return result
            
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def parse_response(raw_response: str) -> dict:
    """پارس پاسخ JSON از LLM"""
    if not raw_response.strip():
        return {"error": "پاسخ خالی از LLM", "raw": "EMPTY"}
    
    # پارس JSON
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    try:
        data = json.loads(cleaned)
        # تبدیل فرمت کوتاه به فرمت کامل
        result = {
            "category": data.get("c") or data.get("category", "unknown"),
            "confidence": data.get("p") or data.get("confidence", 0),
            "_raw": raw_response
        }
        return result
    except json.JSONDecodeError as e:
        return {"error": f"JSON نامعتبر: {e}", "raw": raw_response[:300]}


def classify(query: str, file_analysis: str, model_info: dict) -> dict:
    """انتخاب API مناسب بر اساس مدل"""
    model = model_info['name']
    max_tokens = model_info.get('max_tokens', MAX_TOKENS_DEFAULT)
    
    if "gpt-5" in model:
        return classify_responses_api(query, file_analysis, model, max_tokens)
    else:
        return classify_chat_api(query, file_analysis, model, max_tokens)


# ============================================================================
# مرحله 2: پاسخ‌دهی با پرامپت general
# ============================================================================

def respond_chat_api(query: str, file_analysis: str, model: str) -> dict:
    """پاسخ‌دهی با Chat Completions API"""
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    user_content = query
    if file_analysis:
        user_content = f"{query}\n\n[فایل ضمیمه]: {file_analysis}"
    
    messages = [
        {"role": "system", "content": GENERAL_PROMPT},
        {"role": "user", "content": user_content}
    ]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS_RESPONSE,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content or ""
        
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'completion_tokens', 0)
        
        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
            
    except Exception as e:
        return {"error": str(e)}


def respond_responses_api(query: str, file_analysis: str, model: str) -> dict:
    """پاسخ‌دهی با Responses API (برای gpt-5-nano)"""
    
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    user_content = query
    if file_analysis:
        user_content = f"{query}\n\n[فایل ضمیمه]: {file_analysis}"
    
    full_input = f"{GENERAL_PROMPT}\n\n---\n\n{user_content}"
    
    try:
        response = client.responses.create(
            model=model,
            input=full_input,
            reasoning={"effort": "low"},
            text={"verbosity": "medium"},
            max_output_tokens=MAX_TOKENS_RESPONSE,
        )
        
        # استخراج متن از پاسخ
        answer = ""
        if hasattr(response, 'output') and response.output:
            for output_item in response.output:
                if hasattr(output_item, 'content') and output_item.content:
                    for content_item in output_item.content:
                        if hasattr(content_item, 'text') and content_item.text:
                            answer = content_item.text
                            break
                    if answer:
                        break
        
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'input_tokens', 0) or getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'output_tokens', 0) or getattr(response.usage, 'completion_tokens', 0)
        
        return {
            "answer": answer,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
            
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def respond(query: str, file_analysis: str, model_info: dict) -> dict:
    """انتخاب API مناسب برای پاسخ‌دهی"""
    model = model_info['name']
    
    if "gpt-5" in model:
        return respond_responses_api(query, file_analysis, model)
    else:
        return respond_chat_api(query, file_analysis, model)


def print_response(result: dict, model_label: str):
    """نمایش پاسخ مدل"""
    print(f"\n🤖 {model_label}:")
    print("-" * 40)
    
    if "error" in result:
        print(f"   ❌ خطا: {result['error']}")
    else:
        print(f"   ⬅️ توکن ورودی: {result.get('input_tokens', 0)}")
        print(f"   ➡️ توکن خروجی: {result.get('output_tokens', 0)}")
        print(f"   💬 پاسخ:\n{result.get('answer', '')}")


def print_result(result: dict, model_label: str):
    """نمایش نتیجه کلاسیفیکیشن"""
    print(f"\n🤖 {model_label}:")
    print("-" * 40)
    
    if "error" in result:
        print(f"   ❌ خطا: {result['error']}")
        if result.get('traceback'):
            print(f"   📝 Traceback: {result['traceback'][:500]}")
    else:
        print(f"   📌 دسته‌بندی: {result.get('category', 'N/A')}")
        print(f"   📈 اطمینان: {result.get('confidence', 0)}")
        print(f"   ⬅️ توکن ورودی: {result.get('input_tokens', 0)}")
        print(f"   ➡️ توکن خروجی: {result.get('output_tokens', 0)}")
        print(f"   📝 خام: {result.get('_raw', '')}")


def main():
    print("=" * 60)
    print("🧪 تست کلاسیفیکیشن - مقایسه دو مدل")
    print("=" * 60)
    print(f"LLM: {BASE_URL}")
    print(f"مدل‌ها: {', '.join([m['label'] for m in MODELS])}")
    print("-" * 60)
    
    while True:
        print()
        query = input("📝 سوال خود را وارد کنید (یا 'exit' برای خروج): ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("👋 خداحافظ!")
            break
        
        if not query:
            print("⚠️ سوال نمی‌تواند خالی باشد.")
            continue
        
        file_path = input("📎 آدرس فایل (Enter = بدون فایل): ").strip()
        
        file_analysis = None
        if file_path:
            file_analysis = f"فایل آپلود شده: {file_path}"
        
        # ========== مرحله 1: کلاسیفیکیشن ==========
        print("\n" + "=" * 60)
        print("📊 مرحله 1: کلاسیفیکیشن")
        print("=" * 60)
        
        for model_info in MODELS:
            print(f"\n⏳ در حال پردازش با {model_info['label']}...")
            result = classify(query, file_analysis, model_info)
            print_result(result, model_info['label'])
        
        # ========== مرحله 2: پاسخ‌دهی با پرامپت general ==========
        print("\n" + "=" * 60)
        print("💬 مرحله 2: پاسخ‌دهی (پرامپت general، max_tokens=2048)")
        print("=" * 60)
        
        for model_info in MODELS:
            print(f"\n⏳ در حال پاسخ‌دهی با {model_info['label']}...")
            result = respond(query, file_analysis, model_info)
            print_response(result, model_info['label'])
        
        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
