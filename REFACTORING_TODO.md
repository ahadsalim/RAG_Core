# TODO: Refactoring Tasks

## ✅ انجام شده:
1. ✅ ایجاد فایل مرکزی prompts: `/srv/app/config/prompts.py`
2. ✅ استفاده از prompts مرکزی در `query.py` برای `general_no_business`
3. ✅ استفاده از prompts مرکزی در `query_stream.py` برای `general_no_business` و `invalid` cases

## 🔄 در انتظار:
1. ⏳ Refactor کردن RAG pipeline برای استفاده از `RAGPrompts.get_rag_system_prompt_fa()`
   - فایل: `/srv/app/rag/pipeline.py`
   - خطوط: 516-569 (prompt فارسی)
   - خطوط: 576-615 (prompt انگلیسی)
   - دلیل: prompt خیلی بزرگ است و نیاز به تست دقیق دارد

2. ⏳ استفاده از `LLMConfig` برای temperature و max_tokens
   - فایل‌ها: `query.py`, `query_stream.py`, `classifier.py`
   - مثال:
     ```python
     from app.config.prompts import LLMConfig
     
     # به جای:
     temperature=0.7
     max_tokens=1000
     
     # استفاده کن:
     **LLMConfig.get_config_for_general_questions()
     ```

3. ⏳ استفاده از `ResponseTemplates` برای پاسخ‌های استاندارد
   - مثال: زمانی که منبعی پیدا نشد
   - مثال: زمانی که نیاز به توضیح بیشتر است

## 📝 مزایای Refactoring کامل:

### 1. مدیریت متمرکز
- تمام prompts در یک فایل
- تغییر یک‌جا برای همه endpoints
- نسخه‌گذاری آسان

### 2. A/B Testing
```python
# می‌توانیم به راحتی نسخه‌های مختلف را تست کنیم:
SystemPrompts.get_system_identity_v1()
SystemPrompts.get_system_identity_v2()
```

### 3. چندزبانه‌سازی
```python
# اضافه کردن زبان جدید آسان است:
RAGPrompts.get_rag_system_prompt_fa()  # فارسی
RAGPrompts.get_rag_system_prompt_en()  # انگلیسی
RAGPrompts.get_rag_system_prompt_ar()  # عربی (آینده)
```

### 4. Tuning ساده‌تر
```python
# تنظیمات LLM در یک جا:
LLMConfig.TEMPERATURE_PRECISE = 0.3
LLMConfig.MAX_TOKENS_LONG = 2000
```

### 5. کاهش تکرار کد
- prompts تکراری حذف می‌شوند
- کد تمیزتر و قابل نگهداری‌تر

## 🎯 اولویت‌بندی:

### High Priority (فوری):
- ✅ System prompts برای general questions
- ✅ Invalid prompts

### Medium Priority (مهم):
- ⏳ RAG system prompts
- ⏳ LLM configs

### Low Priority (اختیاری):
- ⏳ Response templates
- ⏳ Classification keywords

## 📊 تأثیر:

| قبل | بعد |
|-----|-----|
| Prompts پراکنده در 5+ فایل | Prompts متمرکز در 1 فایل |
| تغییر prompt = تغییر چند فایل | تغییر prompt = تغییر 1 فایل |
| Hard-coded configs | Centralized configs |
| تکرار کد زیاد | DRY (Don't Repeat Yourself) |

## 🔧 نحوه استفاده:

### مثال 1: استفاده از System Prompt
```python
from app.config.prompts import SystemPrompts

# دریافت تاریخ
current_date_shamsi = "1404/09/10"
current_time_fa = "16:24"

# استفاده از prompt
system_message = SystemPrompts.get_system_identity(
    current_date_shamsi=current_date_shamsi,
    current_time_fa=current_time_fa
)
```

### مثال 2: استفاده از LLM Config
```python
from app.config.prompts import LLMConfig

llm_config = LLMConfig(
    provider=LLMProviderEnum.OPENAI_COMPATIBLE,
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    **LLMConfig.get_config_for_business_questions()  # temperature=0.3, max_tokens=2000
)
```

### مثال 3: استفاده از Response Template
```python
from app.config.prompts import ResponseTemplates

if not sources:
    return ResponseTemplates.no_sources_found()
```

## ⚠️ نکات مهم:

1. **تست کامل بعد از هر تغییر**
   - تست endpoint های non-streaming
   - تست endpoint های streaming
   - تست RAG pipeline

2. **Backward Compatibility**
   - مطمئن شوید تغییرات breaking نباشند
   - API های قدیمی باید کار کنند

3. **Documentation**
   - هر prompt باید docstring داشته باشد
   - مثال‌های استفاده را اضافه کنید

## 📅 Timeline پیشنهادی:

- **Week 1:** ✅ System prompts (انجام شد)
- **Week 2:** RAG prompts refactoring
- **Week 3:** LLM configs refactoring
- **Week 4:** Response templates + testing

---

**آخرین به‌روزرسانی:** 2025-12-01  
**وضعیت:** در حال پیشرفت (30% کامل شده)
