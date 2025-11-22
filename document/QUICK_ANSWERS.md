# پاسخ سریع به سوالات شما

## سوال 1: تنظیمات LLM کجا؟

### ✅ پاسخ کوتاه:
**در سیستم Core (همین سیستم) - فایل `/srv/.env`**

### 🎯 تنظیمات اصلی برای بهبود پاسخ:

```bash
# فایل: /srv/.env

# ========== تنظیمات LLM ==========
LLM_TEMPERATURE=0.7          # 0.0=دقیق، 2.0=خلاق
LLM_MAX_TOKENS=4096          # طول پاسخ
LLM_MODEL="gpt-4-turbo-preview"

# ========== تنظیمات RAG (مهم!) ==========
RAG_TOP_K_RETRIEVAL=20       # تعداد chunks بازیابی
RAG_TOP_K_RERANK=5           # تعداد chunks نهایی
RAG_SIMILARITY_THRESHOLD=0.7 # آستانه شباهت
RAG_MAX_CONTEXT_LENGTH=8192  # طول context
RAG_USE_HYBRID_SEARCH=true   # جستجوی ترکیبی

# ========== Reranking (بهبود کیفیت) ==========
COHERE_API_KEY="..."         # برای reranking
RERANKING_TOP_K=10
```

### 📊 تنظیمات پیشنهادی:

**برای پاسخ‌های دقیق:**
```bash
LLM_TEMPERATURE=0.3
RAG_TOP_K_RETRIEVAL=25
RAG_TOP_K_RERANK=7
RAG_SIMILARITY_THRESHOLD=0.75
```

**برای پاسخ‌های جامع:**
```bash
LLM_TEMPERATURE=0.6
LLM_MAX_TOKENS=6000
RAG_TOP_K_RETRIEVAL=30
RAG_TOP_K_RERANK=10
RAG_MAX_CONTEXT_LENGTH=12000
```

### 🔧 نحوه اعمال:
```bash
# 1. ویرایش
nano /srv/.env

# 2. Restart
cd /srv/deployment/docker
docker-compose restart core-api

# 3. تست
docker exec core-api python3 /app/test.py
```

---

## سوال 2: اطلاعات چت کجا ذخیره می‌شود؟

### ✅ پاسخ کوتاه:
**سیستم Core (همین سیستم) - دیتابیس PostgreSQL**

### 🗄️ ساختار ذخیره‌سازی:

```
Core System (PostgreSQL)
├── user_profiles          → پروفایل کاربران
├── conversations          → همه گفتگوها
├── messages              → همه پیام‌ها
├── query_cache           → کش
└── user_feedback         → بازخورد
```

### 📊 داده‌های ذخیره شده:

#### 1. پروفایل کاربر (`user_profiles`):
```python
{
  "external_user_id": "test-user-123",  # از Users system
  "username": "احمد",
  "tier": "premium",
  "daily_query_count": 12,              # ✅ تعداد query امروز
  "total_query_count": 150,             # ✅ کل query ها
  "total_tokens_used": 45000,           # ✅ کل tokens
  "last_active_at": "2025-11-17..."
}
```

#### 2. گفتگوها (`conversations`):
```python
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "سوالات حقوقی",
  "message_count": 15,                  # ✅ تعداد پیام‌ها
  "total_tokens": 3500,                 # ✅ کل tokens
  "last_message_at": "2025-11-17...",
  "llm_model": "gpt-4",                 # تنظیمات خاص
  "temperature": 0.7
}
```

#### 3. پیام‌ها (`messages`):
```python
{
  "id": "uuid",
  "conversation_id": "uuid",
  "role": "assistant",                  # user/assistant
  "content": "پاسخ سیستم...",
  "tokens": 250,
  "retrieved_chunks": [...],            # ✅ chunks استفاده شده
  "sources": ["doc1", "doc2"],          # ✅ منابع
  "feedback_score": 5,                  # ✅ امتیاز کاربر
  "created_at": "2025-11-17..."
}
```

### 🔍 API های دسترسی:

```bash
# آمار کاربر
GET /api/v1/users/statistics
→ تعداد query، conversation، tokens

# لیست گفتگوها
GET /api/v1/users/conversations
→ همه گفتگوهای کاربر

# پیام‌های یک گفتگو
GET /api/v1/users/conversations/{id}/messages
→ همه پیام‌ها با منابع
```

---

## 🔄 تقسیم مسئولیت

### Users System:
- ✅ Login/Register
- ✅ UI/UX
- ✅ Payment
- ❌ **ذخیره چت ندارد** (فقط cache موقت)

### Core System:
- ✅ **همه گفتگوها** (دائمی)
- ✅ **همه پیام‌ها** (دائمی)
- ✅ **همه سوابق** (دائمی)
- ✅ **همه آمار** (دائمی)
- ✅ پردازش query
- ✅ تنظیمات LLM

---

## 📚 مستندات کامل

برای جزئیات بیشتر:
```bash
/srv/document/LLM_CONFIGURATION_AND_DATA_STORAGE.md
```

این فایل شامل:
- ✅ همه تنظیمات LLM و RAG
- ✅ سناریوهای مختلف
- ✅ ساختار کامل دیتابیس
- ✅ نمودارها و مثال‌ها
- ✅ Best practices

---

## 🎯 خلاصه خلاصه:

1. **تنظیمات LLM**: در Core - فایل `.env`
2. **ذخیره چت**: در Core - دیتابیس PostgreSQL
3. **Users System**: فقط UI و احراز هویت
4. **Core System**: مسئول کامل داده و پردازش
