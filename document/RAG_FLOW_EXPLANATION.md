# 📊 فرایند کامل RAG در سیستم

## 🎯 خلاصه

این سند توضیح می‌دهد که **دقیقاً** چه اتفاقی در سیستم می‌افتد از زمان ورود داده تا پاسخ به کاربر.

---

## 🔄 فرایند کامل (Step by Step)

### 1️⃣ **سیستم Ingest: آماده‌سازی داده**

```
┌─────────────────────────────────────────────┐
│          سیستم INGEST                       │
│  (پورت 8000)                                │
└─────────────────────────────────────────────┘

📄 سند PDF/Word → 📝 استخراج متن → ✂️ تکه‌بندی
                                        ↓
                    🧠 multilingual-e5-base (768 dim)
                                        ↓
                           💾 pgvector (PostgreSQL)
```

**کد**:
- مدل: `intfloat/multilingual-e5-base`
- بُعد: 768
- ذخیره: PostgreSQL با pgvector extension

**مثال**:
```python
# در سیستم Ingest
text = "ماده 1 - قانون کار ایران..."
embedding = model.encode(text)  # shape: (768,)
# ذخیره در pgvector
```

---

### 2️⃣ **انتقال به سیستم Core (Sync)**

```
┌─────────────────────────────────────────────┐
│    SYNC: pgvector → Qdrant                  │
└─────────────────────────────────────────────┘

pgvector (PostgreSQL)  →  API Call  →  Qdrant (Core)
   [768-dim vectors]                    [medium field]
```

**API Endpoint**: `POST /api/v1/sync/embeddings`

**کد**: `/home/ahad/project/core/app/api/v1/endpoints/sync.py`

```python
# خطوط 85-89
synced_count = await sync_service.qdrant_service.upsert_embeddings(
    embeddings_data,
    vector_field="medium"  # ✅ برای 768 بعدی
)
```

**Qdrant Collection Structure**:
```python
{
    "vectors": {
        "small": 512,    # برای مدل‌های کوچک
        "medium": 768,   # ✅ multilingual-e5-base
        "large": 1536,   # OpenAI ada-002
        "default": 3072  # OpenAI text-embedding-3-large
    }
}
```

---

### 3️⃣ **دریافت سوال از کاربر**

```
┌─────────────────────────────────────────────┐
│    کاربر → سیستم Users → سیستم Core         │
└─────────────────────────────────────────────┘

کاربر: "قانون کار ایران چیست؟"
   ↓
Users API (پورت 3001)
   ↓
Core API (پورت 7001): POST /api/v1/query
```

**API Endpoint**: `POST /api/v1/query`

**Request**:
```json
{
  "query": "قانون کار ایران چیست؟",
  "language": "fa",
  "max_results": 5,
  "use_cache": true,
  "use_reranking": true
}
```

---

### 4️⃣ **RAG Pipeline شروع می‌شود**

```
┌─────────────────────────────────────────────┐
│          RAG PIPELINE                        │
│  (/app/rag/pipeline.py)                     │
└─────────────────────────────────────────────┘
```

#### **مرحله A: تمیزکاری و بهبود Query**

**کد**: خطوط 149-173

```python
async def _enhance_query(self, query: RAGQuery) -> str:
    enhanced = query.text
    
    # بهبود فارسی
    if query.language == "fa":
        enhanced = enhanced.replace("ق.م", "قانون مدنی")
        enhanced = enhanced.replace("ق.ت", "قانون تجارت")
        # ...
    
    return enhanced
```

**مثال**:
```
ورودی: "ق.م ایران چیست؟"
خروجی: "قانون مدنی ایران چیست؟"
```

---

#### **مرحله B: Embedding سوال (✅ اصلاح شد!)**

**کد**: خطوط 180-198

```python
async def _generate_embedding(self, text: str) -> List[float]:
    # ✅ استفاده از Local Embedding
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, 
        self.embedder.encode_single,  # multilingual-e5-base
        text
    )
    return embedding.tolist()  # shape: (768,)
```

**قبل از اصلاح** ❌:
```python
# از OpenAI API استفاده می‌کرد (1536 یا 3072 بعد)
return await self.embedder.embed_text(text)  # ❌ مشکل!
```

**بعد از اصلاح** ✅:
```python
# از همان مدلی که در Ingest است استفاده می‌کند
embedding = self.embedder.encode_single(text)  # ✅ درست!
# dimension: 768 (همان multilingual-e5-base)
```

---

#### **مرحله C: جستجو در Qdrant**

**کد**: خطوط 200-241

```python
async def _retrieve_chunks(
    self,
    query_embedding: List[float],  # 768 بعدی
    query_text: str,
    filters: Optional[Dict[str, Any]],
    limit: int
) -> List[RAGChunk]:
    
    # ✅ تشخیص خودکار vector field
    vector_field = self._get_vector_field(len(query_embedding))
    # len(query_embedding) = 768 → vector_field = "medium" ✅
    
    # جستجو در Qdrant
    if settings.rag_use_hybrid_search:
        results = await self.qdrant.hybrid_search(
            query_vector=query_embedding,
            query_text=query_text,
            limit=limit,
            vector_field=vector_field  # ✅ "medium"
        )
    else:
        results = await self.qdrant.search(
            query_vector=query_embedding,
            limit=limit,
            vector_field=vector_field  # ✅ "medium"
        )
    
    return chunks
```

**متد کمکی**:
```python
def _get_vector_field(self, dim: int) -> str:
    """تشخیص خودکار vector field بر اساس بُعد."""
    if dim <= 512:
        return "small"
    elif dim <= 768:
        return "medium"  # ✅ برای multilingual-e5-base
    elif dim <= 1536:
        return "large"
    else:
        return "default"
```

---

#### **مرحله D: Reranking (اختیاری)**

**کد**: خطوط 104-111

```python
# اگر reranking فعال باشد
if query.use_reranking and len(chunks) > query.max_chunks:
    chunks = await self._rerank_chunks(
        enhanced_query,
        chunks,
        top_k=query.max_chunks
    )
```

**چیست**: مرتب‌سازی مجدد نتایج بر اساس ارتباط معنایی دقیق‌تر

---

#### **مرحله E: ساخت پاسخ با LLM**

**کد**: خطوط 114-119

```python
# ساخت پاسخ نهایی
answer, tokens_used = await self._generate_answer(
    query.text,
    chunks,        # تکه‌های مرتبط
    query.language,
    query.conversation_id
)
```

**LLM Provider**: OpenAI-compatible (تنظیم شده در `.env`)

**Prompt Template**:
```
شما یک دستیار قانونی هوشمند هستید.
بر اساس اسناد زیر به سوال پاسخ دهید:

اسناد:
{chunks}

سوال: {query}

پاسخ:
```

---

### 5️⃣ **ذخیره و بازگشت پاسخ**

```python
# ذخیره در PostgreSQL (Core DB)
# - مکالمه (Conversation)
# - پیام کاربر (User Message)
# - پاسخ دستیار (Assistant Message)
# - منابع (Sources)

# بازگشت به API
return QueryResponse(
    answer=answer,
    sources=sources,
    conversation_id=conversation.id,
    message_id=assistant_message.id,
    tokens_used=tokens_used,
    processing_time_ms=processing_time,
    cached=False
)
```

---

## 📊 نمودار کامل فرایند

```
┌──────────────────────────────────────────────────────────────────┐
│                      فرایند کامل RAG                              │
└──────────────────────────────────────────────────────────────────┘

1. ورود داده (Ingest)
   ┌─────────────────┐
   │  PDF/Word/Text  │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │  Text Extract   │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │   Chunking      │
   └────────┬────────┘
            ↓
   ┌─────────────────────────────┐
   │  multilingual-e5-base       │
   │  (768 dim)                  │
   └────────┬────────────────────┘
            ↓
   ┌─────────────────┐
   │   pgvector      │
   │  (PostgreSQL)   │
   └────────┬────────┘
            │
            │ Sync API
            ↓
2. انتقال به Core
   ┌─────────────────┐
   │   Qdrant        │
   │ [medium: 768]   │
   └────────┬────────┘
            │
            │ Query
            ↓
3. پردازش سوال
   ┌─────────────────┐
   │  User Query     │
   │ "قانون کار؟"    │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │  Query Enhance  │
   └────────┬────────┘
            ↓
   ┌─────────────────────────────┐
   │  Local Embedding            │
   │  multilingual-e5-base ✅    │
   │  (768 dim)                  │
   └────────┬────────────────────┘
            ↓
   ┌─────────────────┐
   │ Search Qdrant   │
   │ [medium field]  │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │  Top K Chunks   │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │   Reranking     │
   │   (optional)    │
   └────────┬────────┘
            ↓
   ┌─────────────────┐
   │   LLM Answer    │
   │  (OpenAI API)   │
   └────────┬────────┘
            ↓
4. پاسخ نهایی
   ┌─────────────────┐
   │  Final Answer   │
   │  + Sources      │
   └─────────────────┘
```

---

## ✅ اصلاحات انجام شده

### قبل از اصلاح ❌:
```python
# RAG Pipeline
self.embedder = OpenAIEmbedding()  # ❌ 1536 یا 3072 بعد

# Query embedding
embedding = await self.embedder.embed_text(text)  # ❌ OpenAI API

# مشکل: بُعد embeddings تطابق نداشت!
# - Qdrant: 768 بعد (multilingual-e5-base)
# - Query: 1536+ بعد (OpenAI)
# نتیجه: جستجو کار نمی‌کرد! 🔴
```

### بعد از اصلاح ✅:
```python
# RAG Pipeline
self.embedder = get_local_embedding_service()  # ✅ 768 بعد

# Query embedding
embedding = self.embedder.encode_single(text)  # ✅ Local model

# درست: بُعد embeddings یکسان است!
# - Qdrant: 768 بعد (multilingual-e5-base)
# - Query: 768 بعد (multilingual-e5-base)
# نتیجه: جستجو کامل کار می‌کند! 🟢
```

---

## 🔍 نقاط کلیدی

### 1. **یکسان بودن مدل Embedding**
✅ هم در Ingest و هم در Core از `multilingual-e5-base` استفاده می‌شود

### 2. **Named Vectors در Qdrant**
✅ از `medium` field برای 768 بعدی استفاده می‌شود

### 3. **تشخیص خودکار**
✅ سیستم به صورت خودکار vector field را بر اساس dimension تشخیص می‌دهد

### 4. **کارایی**
✅ Local embedding = رایگان + سریع + حفظ حریم خصوصی

---

## 📁 فایل‌های مهم

| فایل | مسئولیت |
|------|---------|
| `app/rag/pipeline.py` | RAG Pipeline اصلی |
| `app/api/v1/endpoints/query.py` | Query API endpoint |
| `app/api/v1/endpoints/sync.py` | Sync از Ingest |
| `app/services/local_embedding_service.py` | Local embedding |
| `app/services/qdrant_service.py` | Qdrant operations |
| `app/llm/openai_provider.py` | LLM provider |

---

## 🧪 تست فرایند

### تست 1: Embedding یکسان است؟
```bash
# در Core
curl -X POST http://localhost:7001/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "قانون کار"}' \
  | jq '.data[0].embedding | length'

# خروجی: 768 ✅
```

### تست 2: Sync کار می‌کند؟
```bash
curl -X POST http://localhost:7001/api/v1/sync/embeddings \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "embeddings": [{
      "id": "test-1",
      "vector": [0.1, 0.2, ...],  // 768 عدد
      "text": "تست",
      "document_id": "doc-1"
    }]
  }'
```

### تست 3: Query کار می‌کند؟
```bash
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون کار ایران چیست؟",
    "language": "fa"
  }'
```

---

## 🎉 نتیجه

**همه فرایند به درستی کار می‌کند:**

1. ✅ داده‌ها در Ingest با `multilingual-e5-base` embed می‌شوند
2. ✅ به Qdrant منتقل می‌شوند (vector field: `medium`)
3. ✅ Query هم با همان مدل embed می‌شود
4. ✅ جستجو در Qdrant با بُعد یکسان
5. ✅ پاسخ با LLM ساخته می‌شود
6. ✅ نتیجه به کاربر برمی‌گردد

**هیچ تناقضی در مدل‌ها یا بُعدها وجود ندارد!** 🎊
