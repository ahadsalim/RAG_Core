# تقسیم وظایف و مسئولیت‌های زیرسیستم‌های RAG

## نمای کلی معماری

```
┌──────────────────────────────────────────────────────────────┐
│                         Users System                          │
│  (Frontend + User Management + Billing + Authentication)      │
└───────────────┬────────────────────────┬─────────────────────┘
                │                        │
                │     JWT + Query        │ 
                ▼                        ▼
┌──────────────────────────────────────────────────────────────┐
│                         Core System                           │
│         (RAG Pipeline + Query Processing + Caching)           │
└───────────────┬────────────────────────┬─────────────────────┘
                │                        │
                │    Embeddings          │
                ▼                        ▼
┌──────────────────────────────────────────────────────────────┐
│                        Ingest System                          │
│      (Data Collection + Processing + Embedding + OCR)         │
└───────────────────────────────────────────────────────────────┘
```

## 1. زیرسیستم Ingest (جمع‌آوری و پردازش داده)

### مسئولیت‌های اصلی:

#### 1.1 جمع‌آوری داده (Data Collection)
```python
# مسئول جمع‌آوری از منابع مختلف:
- Web Scraping
- API Integration  
- File Upload (PDF, Word, Excel)
- Database Import
- RSS/News Feeds
```

#### 1.2 پردازش و تبدیل داده (Data Processing)
```python
# عملیات پردازش:
- OCR برای اسناد اسکن شده
- استخراج متن از PDF/Word
- پاکسازی و نرمال‌سازی متن
- تشخیص زبان
- استخراج متادیتا
```

#### 1.3 تولید امبدینگ (Embedding Generation)
```python
# مدل: intfloat/multilingual-e5-base
- تبدیل متن به بردار 768 بعدی
- Chunking استراتژی (512 کاراکتر با 50 overlap)
- نرمال‌سازی بردارها
```

#### 1.4 ذخیره‌سازی موقت (Temporary Storage)
```python
# Database: PostgreSQL + pgvector
Tables:
- documents (اسناد اصلی)
- chunks (قطعات متن)
- embeddings (بردارهای embedding)
- sync_queue (صف همگام‌سازی)
```

### کدهای مربوطه در Core که Ingest استفاده می‌کند:

```python
# APIs که Ingest فراخوانی می‌کند:
POST /api/v1/sync/embeddings      # ارسال امبدینگ‌های جدید
DELETE /api/v1/sync/document/{id}  # حذف سند
GET /api/v1/sync/status           # بررسی وضعیت
GET /api/v1/sync/statistics      # دریافت آمار
```

### خروجی‌های Ingest:
```json
{
  "embedding": {
    "id": "unique-id",
    "vector": [768 dimensional array],
    "text": "chunk text",
    "document_id": "doc-uuid",
    "metadata": {
      "language": "fa",
      "category": "legal",
      "jurisdiction": "Iran",
      // ...
    }
  }
}
```

## 2. زیرسیستم Core (هسته مرکزی RAG)

### مسئولیت‌های اصلی:

#### 2.1 مدیریت Vector Database (Qdrant)
```python
# app/services/qdrant_service.py
- نگهداری بردارهای امبدینگ در Qdrant
- جستجوی semantic (vector search)
- جستجوی hybrid (vector + keyword)
- مدیریت collections و indexes
```

#### 2.2 RAG Pipeline
```python
# app/rag/pipeline.py
class RAGPipeline:
    - Query Enhancement (بهبود query)
    - Embedding Generation (تولید امبدینگ query)
    - Retrieval (بازیابی chunks مرتبط)
    - Reranking (مرتب‌سازی مجدد نتایج)
    - Answer Generation (تولید پاسخ با LLM)
```

#### 2.3 LLM Integration
```python
# app/llm/openai_provider.py
- ارتباط با OpenAI-compatible APIs
- مدیریت prompts
- Streaming responses
- Token management
```

#### 2.4 User Profile Management (محدود)
```python
# app/models/user.py
Tables:
- user_profiles (پروفایل‌های کاربران)
- conversations (مکالمات)
- messages (پیام‌ها)
- query_cache (کش query ها)
- user_feedback (بازخوردها)
```

#### 2.5 Caching & Performance
```python
# Redis برای:
- Query cache
- Session management
- Rate limiting
- Temporary data
```

#### 2.6 Background Tasks (Celery)
```python
# app/tasks/
- sync.py: همگام‌سازی با Ingest
- cleanup.py: پاکسازی cache
- user.py: بروزرسانی آمار کاربران
- notifications.py: ارسال نتایج به Users system
```

### API Endpoints اصلی Core:

```python
# برای Users System:
POST /api/v1/query/                    # پردازش query
POST /api/v1/query/stream              # پردازش streaming
POST /api/v1/query/feedback            # دریافت feedback
GET  /api/v1/users/profile             # پروفایل کاربر
GET  /api/v1/users/conversations       # لیست مکالمات
GET  /api/v1/users/conversations/{id}  # پیام‌های مکالمه

# برای Ingest System:
POST /api/v1/sync/embeddings           # دریافت امبدینگ‌ها
GET  /api/v1/sync/status               # وضعیت sync

# Admin APIs:
GET  /api/v1/admin/stats               # آمار سیستم
POST /api/v1/admin/cache/clear         # پاکسازی cache
```

### کدهای کلیدی Core:

```python
# 1. Query Processing (app/api/v1/endpoints/query.py)
@router.post("/")
async def process_query(request: QueryRequest):
    # بررسی محدودیت کاربر
    # فراخوانی RAG pipeline
    # ذخیره در دیتابیس
    # ارسال نتیجه

# 2. Qdrant Service (app/services/qdrant_service.py)
class QdrantService:
    async def search()      # جستجوی vector
    async def hybrid_search()  # جستجوی hybrid
    async def upsert_embeddings()  # درج امبدینگ

# 3. RAG Pipeline (app/rag/pipeline.py)
class RAGPipeline:
    async def process(query: RAGQuery):
        # 1. Query enhancement
        # 2. Generate embedding
        # 3. Retrieve chunks
        # 4. Rerank results
        # 5. Generate answer
```

## 3. زیرسیستم Users (رابط کاربری و مدیریت کاربران)

### مسئولیت‌های اصلی:

#### 3.1 احراز هویت و مجوزدهی (Authentication & Authorization)
```javascript
// مسئول کامل:
- User registration
- Login/Logout
- Password management
- Multi-factor authentication
- JWT token generation
- Session management
```

#### 3.2 مدیریت اشتراک و پرداخت (Subscription & Billing)
```javascript
// مدیریت کامل:
- Subscription tiers (Free, Basic, Premium, Enterprise)
- Payment processing
- Invoice generation
- Usage tracking
- Quota management
```

#### 3.3 رابط کاربری (User Interface)
```javascript
// Components:
- Query input interface
- Response display (with streaming)
- Conversation history
- Search filters
- Settings panel
- Dashboard
```

#### 3.4 مدیریت تاریخچه محلی (Local History)
```javascript
// ذخیره موقت:
- Recent queries
- Favorite conversations
- User preferences
- UI state
```

#### 3.5 ارتباط با Core API
```javascript
// API Client:
class CoreAPIClient {
    - sendQuery()
    - getConversations()
    - submitFeedback()
    - getUserProfile()
}
```

### نحوه ارتباط Users با Core:

```javascript
// 1. احراز هویت
const token = await generateJWT(user);

// 2. ارسال Query
const response = await fetch('/api/v1/query/', {
    headers: { 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ query, filters })
});

// 3. مدیریت Response
if (response.streaming) {
    handleStreamingResponse(response);
} else {
    displayResponse(response);
}
```

## جدول تفکیک مسئولیت‌ها

| عملکرد | Ingest | Core | Users |
|--------|--------|------|-------|
| **Data Collection** | ✅ مسئول اصلی | ❌ | ❌ |
| **Text Processing** | ✅ مسئول اصلی | ❌ | ❌ |
| **Embedding Generation** | ✅ برای داده‌های جدید | ✅ برای queries | ❌ |
| **Vector Storage** | ❌ | ✅ مسئول اصلی (Qdrant) | ❌ |
| **Query Processing** | ❌ | ✅ مسئول اصلی | ❌ |
| **Answer Generation** | ❌ | ✅ مسئول اصلی (LLM) | ❌ |
| **User Authentication** | ❌ | ⚠️ اعتبارسنجی JWT | ✅ مسئول اصلی |
| **Subscription Management** | ❌ | ⚠️ بررسی tier | ✅ مسئول اصلی |
| **Payment Processing** | ❌ | ❌ | ✅ مسئول اصلی |
| **UI/UX** | ❌ | ❌ | ✅ مسئول اصلی |
| **Conversation History** | ❌ | ✅ ذخیره اصلی | ⚠️ کش موقت |
| **Usage Analytics** | ⚠️ آمار پردازش | ✅ آمار queries | ✅ آمار کاربران |
| **Cache Management** | ❌ | ✅ مسئول اصلی | ⚠️ کش محلی |
| **Rate Limiting** | ❌ | ✅ مسئول اصلی | ⚠️ بررسی اولیه |

## جریان داده (Data Flow)

### 1. جریان ورود داده جدید:
```
Document Upload (Users) 
    → Processing (Ingest) 
    → Embedding (Ingest)
    → Sync to Core (API)
    → Store in Qdrant (Core)
```

### 2. جریان پردازش Query:
```
User Query (Users UI)
    → JWT Auth (Users)
    → Send to Core (API)
    → Check Limits (Core)
    → RAG Pipeline (Core)
    → Return Response (Core)
    → Display (Users UI)
```

### 3. جریان Feedback:
```
User Feedback (Users UI)
    → Send to Core (API)
    → Store in DB (Core)
    → Update Models (Core)
    → Analytics (Core/Users)
```

## نکات مهم برای توسعه‌دهندگان

### برای تیم Ingest:
1. **Embedding Model**: حتماً از `multilingual-e5-base` با 768 dimension استفاده کنید
2. **Batch Size**: حداکثر 100 امبدینگ در هر درخواست
3. **Metadata**: تمام فیلدهای metadata مشخص شده را پر کنید
4. **Error Handling**: برای sync failures، retry با exponential backoff
5. **Monitoring**: آمار sync را مرتب چک کنید

### برای تیم Core:
1. **Database**: هم PostgreSQL و هم Qdrant باید همیشه sync باشند
2. **Caching**: برای queries پرتکرار حتماً cache فعال باشد
3. **Rate Limiting**: محدودیت‌ها بر اساس user tier اعمال شود
4. **Monitoring**: همه metrics در Prometheus ثبت شود
5. **Security**: JWT validation برای همه endpoints اجباری است

### برای تیم Users:
1. **JWT Token**: حداکثر 30 دقیقه اعتبار، با refresh token
2. **Error Handling**: همه error codes را handle کنید
3. **Streaming**: برای تجربه بهتر، streaming را پیاده‌سازی کنید
4. **Local Cache**: برای کاهش latency، نتایج اخیر را cache کنید
5. **Analytics**: همه user interactions را track کنید

## محیط‌های Deployment

### Development Environment:
```yaml
Ingest: http://localhost:8000
Core:   http://localhost:7001
Users:  http://localhost:3001
Qdrant: http://localhost:7333
Redis:  localhost:6379
```

### Production Environment:
```yaml
Ingest: https://ingest.domain.com
Core:   https://core.domain.com
Users:  https://app.domain.com
Qdrant: Internal network only
Redis:  Internal network only
```

## خلاصه

این معماری سه‌لایه امکان توسعه مستقل هر زیرسیستم را فراهم می‌کند:

- **Ingest**: مستقل در جمع‌آوری و پردازش داده
- **Core**: هسته مرکزی با تمرکز بر RAG و performance
- **Users**: رابط کاربری با تمرکز بر UX و مدیریت کاربران

هر تیم می‌تواند با رعایت API contracts مشخص شده، به صورت مستقل توسعه دهد.
