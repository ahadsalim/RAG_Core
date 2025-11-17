# راهنمای تنظیمات LLM و ذخیره‌سازی داده‌های کاربر

## 📋 فهرست مطالب
1. [تنظیمات LLM برای بهبود پاسخ](#1-تنظیمات-llm-برای-بهبود-پاسخ)
2. [ذخیره‌سازی اطلاعات چت و سوابق کاربر](#2-ذخیره‌سازی-اطلاعات-چت-و-سوابق-کاربر)
3. [تقسیم مسئولیت بین Core و Users](#3-تقسیم-مسئولیت-بین-core-و-users)

---

## 1. تنظیمات LLM برای بهبود پاسخ

### 🎯 کجا باید تنظیمات را انجام دهید؟

**پاسخ: در سیستم Core (این سیستم)**

سیستم Core مسئول کامل پردازش query و تولید پاسخ است. تنظیمات LLM در Core انجام می‌شود.

---

### ⚙️ تنظیمات موجود در Core

#### 1.1 تنظیمات پایه LLM (در `/srv/.env`):

```bash
# ==================================================================
# LLM Configuration
# ==================================================================

# API Key (اجباری)
LLM_API_KEY="sk-proj-..."

# Base URL (اختیاری - برای API های غیر OpenAI)
LLM_BASE_URL=""  # خالی = OpenAI default
# یا
LLM_BASE_URL="https://api.groq.com/openai/v1"  # برای Groq
# یا
LLM_BASE_URL="https://api.together.xyz/v1"  # برای Together.ai

# Model Name
LLM_MODEL="gpt-4-turbo-preview"  # یا gpt-4, gpt-3.5-turbo, llama-3.1-70b-versatile

# Maximum Output Tokens
LLM_MAX_TOKENS=4096  # حداکثر طول پاسخ

# Temperature (خلاقیت)
LLM_TEMPERATURE=0.7  # 0.0 = دقیق، 2.0 = خلاق
```

---

#### 1.2 تنظیمات RAG (در `/srv/.env`):

این تنظیمات مستقیماً بر کیفیت پاسخ تأثیر دارند:

```bash
# ==================================================================
# RAG Settings - تنظیمات بازیابی و تولید پاسخ
# ==================================================================

# تعداد chunks برای بازیابی اولیه
RAG_TOP_K_RETRIEVAL=20  # پیشنهاد: 15-30

# تعداد chunks نهایی بعد از reranking
RAG_TOP_K_RERANK=5  # پیشنهاد: 3-7

# آستانه شباهت (similarity threshold)
RAG_SIMILARITY_THRESHOLD=0.7  # پیشنهاد: 0.65-0.80

# حداکثر طول context برای LLM
RAG_MAX_CONTEXT_LENGTH=8192  # پیشنهاد: 6000-12000

# استفاده از Hybrid Search (Vector + BM25)
RAG_USE_HYBRID_SEARCH=true  # پیشنهاد: true

# وزن BM25 در hybrid search
RAG_BM25_WEIGHT=0.3  # پیشنهاد: 0.2-0.4

# وزن Vector در hybrid search
RAG_VECTOR_WEIGHT=0.7  # پیشنهاد: 0.6-0.8
```

---

#### 1.3 تنظیمات Reranking (بهبود کیفیت):

```bash
# ==================================================================
# Reranking Configuration
# ==================================================================

# Cohere API Key (برای reranking)
COHERE_API_KEY="your-cohere-api-key"  # اختیاری اما توصیه می‌شود

# Reranking Model
RERANKING_MODEL="rerank-multilingual-v2.0"

# تعداد نتایج برای rerank
RERANKING_TOP_K=10  # پیشنهاد: 8-15
```

---

### 📊 تنظیمات پیشنهادی برای سناریوهای مختلف

#### سناریو 1: پاسخ‌های دقیق و واقعی (Factual)
```bash
LLM_TEMPERATURE=0.3
RAG_TOP_K_RETRIEVAL=25
RAG_TOP_K_RERANK=7
RAG_SIMILARITY_THRESHOLD=0.75
RAG_USE_HYBRID_SEARCH=true
```

#### سناریو 2: پاسخ‌های خلاقانه و توضیحی
```bash
LLM_TEMPERATURE=0.8
RAG_TOP_K_RETRIEVAL=15
RAG_TOP_K_RERANK=5
RAG_SIMILARITY_THRESHOLD=0.65
RAG_USE_HYBRID_SEARCH=true
```

#### سناریو 3: پاسخ‌های سریع (Performance)
```bash
LLM_TEMPERATURE=0.5
RAG_TOP_K_RETRIEVAL=10
RAG_TOP_K_RERANK=3
RAG_SIMILARITY_THRESHOLD=0.70
RAG_USE_HYBRID_SEARCH=false
COHERE_API_KEY=""  # غیرفعال کردن reranking
```

#### سناریو 4: پاسخ‌های جامع (Comprehensive)
```bash
LLM_TEMPERATURE=0.6
LLM_MAX_TOKENS=6000
RAG_TOP_K_RETRIEVAL=30
RAG_TOP_K_RERANK=10
RAG_SIMILARITY_THRESHOLD=0.65
RAG_MAX_CONTEXT_LENGTH=12000
RAG_USE_HYBRID_SEARCH=true
```

---

### 🎨 تنظیمات پیشرفته در سطح Conversation

کاربران می‌توانند برای هر conversation تنظیمات خاص داشته باشند:

```python
# در دیتابیس Core، جدول conversations:
{
  "llm_model": "gpt-4",           # مدل خاص این conversation
  "temperature": 0.8,              # temperature خاص
  "max_tokens": 5000,              # حداکثر tokens
  "context": {                     # context اضافی
    "domain": "legal",
    "jurisdiction": "Iran",
    "language_style": "formal"
  }
}
```

این تنظیمات در Core ذخیره و اعمال می‌شوند.

---

### 🔧 نحوه اعمال تغییرات

#### روش 1: تغییر در `.env` (Global)
```bash
# 1. ویرایش فایل
nano /srv/.env

# 2. تغییر تنظیمات
LLM_TEMPERATURE=0.5
RAG_TOP_K_RERANK=7

# 3. Restart سرویس
cd /srv/deployment/docker
docker-compose restart core-api

# 4. بررسی logs
docker-compose logs -f core-api
```

#### روش 2: تغییر در Runtime (برای تست)
```python
# از طریق Admin API (در آینده)
POST /api/v1/admin/config
{
  "rag_top_k_rerank": 7,
  "llm_temperature": 0.5
}
```

---

### 📈 مانیتورینگ و بهینه‌سازی

#### بررسی کیفیت پاسخ‌ها:
```bash
# لاگ‌های مربوط به RAG pipeline
docker-compose logs core-api | grep "RAG pipeline"

# آمار query ها
curl -X GET http://localhost:7001/api/v1/admin/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

#### Metrics مهم:
- **Processing Time**: زمان پردازش query
- **Chunks Retrieved**: تعداد chunks بازیابی شده
- **Similarity Scores**: امتیازات شباهت
- **Token Usage**: مصرف token
- **User Feedback**: بازخورد کاربران

---

## 2. ذخیره‌سازی اطلاعات چت و سوابق کاربر

### 🗄️ پاسخ کوتاه:

**سیستم Core مسئول ذخیره همه اطلاعات چت، سوابق، و تعداد گفتگوها است.**

---

### 📊 ساختار ذخیره‌سازی در Core

#### دیتابیس: PostgreSQL در Core System

```sql
-- جداول اصلی:

1. user_profiles          -- پروفایل کاربران
2. conversations          -- گفتگوهای کاربران
3. messages              -- پیام‌های هر گفتگو
4. query_cache           -- کش query ها
5. user_feedback         -- بازخورد کاربران
```

---

### 🔍 جزئیات جداول

#### 2.1 جدول `user_profiles`

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY,
    external_user_id VARCHAR(100) UNIQUE NOT NULL,  -- ID از Users system
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),
    
    -- Subscription
    tier VARCHAR(20) DEFAULT 'free',  -- free, basic, premium, enterprise
    daily_query_limit INTEGER DEFAULT 50,
    daily_query_count INTEGER DEFAULT 0,
    total_query_count INTEGER DEFAULT 0,
    
    -- Preferences
    preferences JSONB DEFAULT '{}',
    language VARCHAR(10) DEFAULT 'fa',
    timezone VARCHAR(50) DEFAULT 'Asia/Tehran',
    
    -- Statistics
    last_active_at TIMESTAMP WITH TIME ZONE,
    total_tokens_used INTEGER DEFAULT 0,
    total_feedback_given INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**داده‌های ذخیره شده:**
- ✅ اطلاعات پایه کاربر
- ✅ محدودیت‌ها و سطح اشتراک
- ✅ تنظیمات شخصی
- ✅ آمار کلی استفاده

---

#### 2.2 جدول `conversations`

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    
    -- Metadata
    title VARCHAR(255),                    -- عنوان گفتگو
    summary TEXT,                          -- خلاصه گفتگو
    message_count INTEGER DEFAULT 0,       -- تعداد پیام‌ها
    total_tokens INTEGER DEFAULT 0,        -- مجموع tokens
    
    -- Context
    context JSONB DEFAULT '{}',            -- context اضافی
    
    -- Model Settings (per conversation)
    llm_model VARCHAR(100),                -- مدل LLM
    temperature FLOAT DEFAULT 0.7,         -- temperature
    max_tokens INTEGER DEFAULT 4096,       -- حداکثر tokens
    
    -- Timestamps
    last_message_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_conversation_user ON conversations(user_id);
CREATE INDEX idx_conversation_last_message ON conversations(last_message_at);
```

**داده‌های ذخیره شده:**
- ✅ همه گفتگوهای کاربر
- ✅ تعداد پیام‌ها در هر گفتگو
- ✅ تنظیمات خاص هر گفتگو
- ✅ زمان آخرین پیام

---

#### 2.3 جدول `messages`

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Message Content
    role VARCHAR(20) NOT NULL,             -- user, assistant, system
    content TEXT NOT NULL,                 -- محتوای پیام
    
    -- Metadata
    tokens INTEGER DEFAULT 0,              -- تعداد tokens
    processing_time_ms INTEGER,            -- زمان پردازش
    
    -- Retrieved Context (برای پیام‌های assistant)
    retrieved_chunks JSONB,                -- chunks بازیابی شده
    sources JSONB,                         -- منابع استفاده شده
    
    -- User Feedback
    feedback_score INTEGER,                -- 1-5 یا thumbs up/down
    feedback_comment TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_message_conversation ON messages(conversation_id);
CREATE INDEX idx_message_created ON messages(created_at);
```

**داده‌های ذخیره شده:**
- ✅ همه پیام‌های کاربر و assistant
- ✅ منابع و chunks استفاده شده
- ✅ بازخورد کاربر
- ✅ زمان و metadata

---

### 📈 آمار و گزارش‌ها

#### API های آماری در Core:

```python
# 1. آمار کاربر
GET /api/v1/users/statistics
Response:
{
  "total_queries": 150,
  "daily_queries": 12,
  "total_conversations": 25,
  "total_tokens_used": 45000,
  "average_response_time_ms": 2500
}

# 2. لیست گفتگوها
GET /api/v1/users/conversations
Response:
{
  "conversations": [
    {
      "id": "uuid",
      "title": "سوالات حقوقی",
      "message_count": 15,
      "last_message_at": "2025-11-17T10:00:00Z",
      "created_at": "2025-11-15T08:00:00Z"
    }
  ],
  "total": 25,
  "page": 1
}

# 3. پیام‌های یک گفتگو
GET /api/v1/users/conversations/{id}/messages
Response:
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "سوال کاربر",
      "created_at": "2025-11-17T10:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "پاسخ سیستم",
      "sources": ["doc1", "doc2"],
      "tokens": 250,
      "created_at": "2025-11-17T10:00:05Z"
    }
  ]
}
```

---

## 3. تقسیم مسئولیت بین Core و Users

### 🔄 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Users System                            │
│  - احراز هویت (Login/Register)                              │
│  - مدیریت پرداخت و اشتراک                                   │
│  - رابط کاربری (UI)                                         │
│  - ذخیره موقت محلی (Local Storage)                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ JWT Token + Query
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Core System                             │
│  ✅ ذخیره همه گفتگوها و پیام‌ها                            │
│  ✅ ذخیره سوابق و آمار کاربر                               │
│  ✅ پردازش query و تولید پاسخ                              │
│  ✅ مدیریت context و تاریخچه                               │
│  ✅ محاسبه tokens و هزینه                                  │
└─────────────────────────────────────────────────────────────┘
```

---

### 📋 جدول تقسیم وظایف

| مسئولیت | Users System | Core System |
|---------|--------------|-------------|
| **احراز هویت** | ✅ کامل | ❌ فقط JWT validation |
| **مدیریت اشتراک** | ✅ کامل | ❌ فقط check limit |
| **ذخیره گفتگوها** | ❌ فقط cache موقت | ✅ **ذخیره دائمی** |
| **ذخیره پیام‌ها** | ❌ فقط cache موقت | ✅ **ذخیره دائمی** |
| **آمار کاربر** | ❌ نمایش فقط | ✅ **محاسبه و ذخیره** |
| **تعداد query** | ❌ | ✅ **ذخیره و محدودیت** |
| **Token usage** | ❌ | ✅ **محاسبه و ذخیره** |
| **پردازش query** | ❌ | ✅ **کامل** |
| **تنظیمات LLM** | ❌ | ✅ **کامل** |
| **RAG Pipeline** | ❌ | ✅ **کامل** |

---

### 🔑 نکات کلیدی

#### 1. Users System:
```javascript
// فقط مسئول:
- Login/Register
- UI/UX
- Payment
- Local caching (برای سرعت)

// نمونه Local Storage:
localStorage.setItem('recent_queries', JSON.stringify([
  {query: "سوال 1", timestamp: "..."},
  {query: "سوال 2", timestamp: "..."}
]));
```

#### 2. Core System:
```python
# مسئول کامل:
- همه داده‌های چت (conversations + messages)
- همه سوابق کاربر (history)
- همه آمار (statistics)
- پردازش query
- تنظیمات LLM

# نمونه ذخیره:
conversation = Conversation(
    user_id=user.id,
    title="گفتگوی جدید",
    message_count=0,
    total_tokens=0
)
db.add(conversation)
```

---

### 🔄 نحوه همکاری

```python
# 1. کاربر در Users System login می‌کند
# Users System:
user = authenticate(username, password)
jwt_token = generate_jwt(user.id)  # external_user_id

# 2. کاربر query می‌فرستد
# Users System → Core:
POST /api/v1/query/
Headers: {
  "Authorization": "Bearer {jwt_token}"
}
Body: {
  "query": "سوال کاربر",
  "conversation_id": "uuid-optional"
}

# 3. Core پردازش و ذخیره می‌کند
# Core System:
- Validate JWT
- Get/Create user profile
- Get/Create conversation
- Process query
- Save messages
- Update statistics
- Return response

# 4. Users System نمایش می‌دهد
# Users System:
- Display response
- Update UI
- Cache locally (optional)
```

---

## 🎯 خلاصه پاسخ سوالات

### سوال 1: تنظیمات LLM کجا؟
**پاسخ:** در سیستم **Core** (همین سیستم)
- فایل: `/srv/.env`
- تنظیمات: `LLM_*` و `RAG_*`
- Restart: `docker-compose restart core-api`

### سوال 2: اطلاعات چت کجا ذخیره می‌شود؟
**پاسخ:** در سیستم **Core** (همین سیستم)
- دیتابیس: PostgreSQL در Core
- جداول: `user_profiles`, `conversations`, `messages`
- همه سوابق، آمار، و تعداد گفتگوها در Core است

---

## 📚 منابع بیشتر

- [تنظیمات Embedding](./EMBEDDING_CONFIGURATION_GUIDE.md)
- [مستندات Core](./1_CORE_SYSTEM_DOCUMENTATION.md)
- [تقسیم وظایف](./4_SUBSYSTEMS_RESPONSIBILITIES.md)
