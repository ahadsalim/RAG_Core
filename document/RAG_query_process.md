# 📊 فرآیند کامل تولید پاسخ RAG

## 🎯 نمودار کلی فرآیند

```
سیستم کاربران → API Gateway → Core System → RAG Pipeline → LLMs → Qdrant → پاسخ نهایی → سیستم کاربران
```

---

## 📍 مرحله 1: دریافت درخواست از سیستم کاربران

### فایل: `/srv/app/api/v1/endpoints/query.py` (خط 219-288)

```python
@router.post("/")
async def process_query(
    request: QueryRequest,  # شامل: query, language, max_results, filters, ...
    user_id: str = Depends(get_current_user_id)  # JWT authentication
)
```

**ورودی از سیستم کاربران:**
```json
{
  "query": "ماده ده قانون چلمنگان چی می گه؟",
  "language": "fa",
  "max_results": 5,
  "use_cache": true,
  "use_reranking": true,
  "filters": null
}
```

**کارهای انجام شده:**
1. ✅ **Authentication**: بررسی JWT token و شناسایی کاربر
2. ✅ **بررسی User Profile**: 
   - اگر کاربر جدید است → ایجاد profile
   - بررسی محدودیت روزانه (daily query limit)
3. ✅ **مدیریت Conversation**:
   - اگر conversation_id داده شده → بازیابی
   - اگر نه → ایجاد conversation جدید
4. ✅ **ساخت RAGQuery object**:
```python
rag_query = RAGQuery(
    text=request.query,
    user_id=str(user.id),
    conversation_id=str(conversation.id),
    language=request.language,
    max_chunks=request.max_results,
    filters=request.filters,
    use_cache=request.use_cache,
    use_reranking=request.use_reranking,
    user_preferences=request.user_preferences
)
```

---

## 📍 مرحله 2: ورود به RAG Pipeline

### فایل: `/srv/app/rag/pipeline.py` - متد `process()` (خط 75-179)

```python
pipeline = RAGPipeline()
rag_response = await pipeline.process(rag_query)
```

### 🔹 Step 0: دسته‌بندی سوال با LLM (خط 88-109)

**هدف:** تشخیص اینکه سوال واقعی است یا احوالپرسی/چرت‌وپرت

```python
classification = await self.classifier.classify(query.text, query.language)
```

#### فایل: `/srv/app/llm/classifier.py` (خط 45-86)

**Prompt ارسالی به LLM:**
```python
system_prompt = """شما یک دسته‌بندی کننده هوشمند سوالات هستید.

دسته‌بندی‌ها:
1. greeting - احوالپرسی
2. chitchat - گفتگوی عمومی
3. invalid - محتوای نامعتبر
4. business_question - سوال واقعی درباره کسب و کار/قانون

خروجی JSON:
{
  "category": "...",
  "confidence": 0.0-1.0,
  "direct_response": "...",
  "reason": "..."
}
"""

user_message = f"متن کاربر: {query}"
```

**فراخوانی LLM:**
```python
# استفاده از gpt-4o-mini با temperature=0.2
response = await self.llm.generate(messages)
```

**ارزیابی پاسخ:**
```python
result = self._parse_classification_response(response.content)

if result.category != "business_question":
    # پاسخ مستقیم بدون RAG
    return RAGResponse(
        answer=result.direct_response,
        chunks=[],
        sources=[],
        ...
    )
# اگر business_question بود → ادامه به RAG
```

---

### 🔹 Step 1: بررسی Cache (خط 114-118)

```python
if query.use_cache:
    cached_response = await self._check_cache(query)
    if cached_response:
        return cached_response  # بازگشت سریع
```

**Cache Key:**
```python
key = md5(f"{query.text}|{language}|{max_chunks}|{filters}")
# مثال: "rag:cache:a3f5d8e9..."
```

---

### 🔹 Step 2: بهبود Query با LLM (خط 121)

```python
enhanced_query = await self._enhance_query(query)
```

#### فایل: `/srv/app/rag/pipeline.py` - متد `_enhance_query()` (خط 204-273)

**Prompt ارسالی به LLM:**
```python
system_prompt = """شما یک متخصص جستجوی اسناد حقوقی هستید.

کارهای شما:
1. اختصارات قوانین را باز کنید (ق.م → قانون مدنی)
2. اعداد فارسی را به انگلیسی تبدیل کنید (۱۲۳ → 123)
3. اعداد کلامی را به عددی تبدیل کنید (ده → 10)
4. املای اشتباه را تصحیح کنید
5. کلمات مترادف مهم اضافه کنید

مثال:
ورودی: "ماده ده قانون چلمنگان"
خروجی: "ماده 10 قانون چلمنگان"

فقط query بهینه شده را برگردانید."""

user_message = f"سوال کاربر: {query.text}"
```

**فراخوانی LLM:**
```python
response = await self.llm.generate(
    messages,
    temperature=0.1,  # کم برای consistency
    max_tokens=200
)

enhanced = response.content.strip()
```

**مثال:**
```
ورودی: "ماده ده قانون چلمنگان چی می گه؟"
↓
خروجی: "ماده 10 قانون چلمنگان"
```

---

### 🔹 Step 3: تولید Embedding (خط 124)

```python
query_embedding = await self._generate_embedding(enhanced_query)
```

#### فایل: `/srv/app/services/embedding_service.py` (خط 142-153)

```python
# استفاده از مدل local: intfloat/multilingual-e5-large
embedding = embedder.encode_single(text)  # numpy array [1024]
return embedding.tolist()  # تبدیل به list
```

**خروجی:**
```python
query_embedding = [0.023, -0.145, 0.089, ..., 0.234]  # 1024 dimensions
```

---

### 🔹 Step 4: جستجو در Qdrant (خط 127-132)

```python
chunks = await self._retrieve_chunks(
    query_embedding,
    enhanced_query,
    query.filters,
    limit=query.max_chunks * 3  # 5 * 3 = 15 chunks
)
```

#### فایل: `/srv/app/rag/pipeline.py` - متد `_retrieve_chunks()` (خط 274-349)

**تشخیص Vector Field:**
```python
vector_field = self._get_vector_field(len(query_embedding))
# برای 1024 dim → "large"
```

**انتخاب نوع جستجو:**
```python
if settings.rag_use_hybrid_search:  # True
    results = await self.qdrant.hybrid_search(...)
else:
    results = await self.qdrant.search(...)
```

#### فایل: `/srv/app/services/qdrant_service.py` - متد `hybrid_search()` (خط 319-371)

**⚠️ توجه:** بعد از رفع bug، hybrid search فعلاً فقط vector search است:

```python
async def hybrid_search(...):
    # فقط vector search با threshold پایین‌تر
    vector_results = await self.search(
        query_vector=query_vector,
        limit=limit,
        score_threshold=0.4,  # کاهش یافته برای recall بهتر
        filters=filters,
        vector_field="large"
    )
    return vector_results
```

#### فایل: `/srv/app/services/qdrant_service.py` - متد `search()` (خط 242-317)

**ساخت Filters:**
```python
filter_conditions = []
if filters:
    for key, value in filters.items():
        filter_conditions.append(
            FieldCondition(key=key, match=MatchValue(value=value))
        )

search_filter = Filter(must=filter_conditions) if filter_conditions else None
```

**فراخوانی Qdrant:**
```python
results = self.client.search(
    collection_name="legal_documents",
    query_vector=("large", query_embedding),  # Named vector
    limit=15,
    score_threshold=0.4,
    query_filter=search_filter,
    with_payload=True
)
```

**پاسخ Qdrant:**
```python
[
    {
        "id": "abc123",
        "score": 0.87,
        "payload": {
            "text": "ماده 10 - متن ماده...",
            "document_id": "doc_456",
            "metadata": {
                "work_title": "قانون چلمنگان",
                "unit_number": "10",
                "unit_type": "article",
                ...
            }
        }
    },
    ...
]
```

**تبدیل به RAGChunk:**
```python
chunks = []
for result in results:
    chunk = RAGChunk(
        text=result["text"],
        score=result.get("score", 0.0),
        source=result.get("source", "unknown"),
        metadata=result.get("metadata", {}),
        document_id=result.get("document_id")
    )
    chunks.append(chunk)
```

**لاگ:**
```python
logger.info(
    "Retrieved chunks",
    num_chunks=len(chunks),  # مثلاً 12
    top_scores=[0.87, 0.82, 0.79]
)
```

---

### 🔹 Step 5: Reranking (خط 143-159)

```python
if query.use_reranking and len(chunks) > query.max_chunks:
    chunks = await self._rerank_chunks(
        enhanced_query,
        chunks,
        top_k=query.max_chunks  # 5
    )
else:
    chunks = chunks[:query.max_chunks]
```

#### فایل: `/srv/app/rag/pipeline.py` - متد `_rerank_chunks()` (خط 351-385)

**⚠️ توجه:** Cohere reranker غیرفعال است (API key خالی)

```python
if settings.cohere_api_key and self.reranker:
    # استفاده از Cohere reranker
    ...
else:
    # Fallback: مرتب‌سازی بر اساس score
    return sorted(chunks, key=lambda x: x.score, reverse=True)[:top_k]
```

**خروجی:**
```python
# 5 chunk برتر
chunks = [chunk1, chunk2, chunk3, chunk4, chunk5]
```

---

### 🔹 Step 6: تولید پاسخ با LLM (خط 168-174)

```python
answer, tokens_used = await self._generate_answer(
    query.text,
    chunks,
    query.language,
    query.conversation_id,
    query.user_preferences
)
```

#### فایل: `/srv/app/rag/pipeline.py` - متد `_generate_answer()` (خط 387-457)

**ساخت Context:**
```python
context_parts = []
for i, chunk in enumerate(chunks, 1):
    source_info = f"[منبع {i}]"
    work_title = chunk.metadata.get("work_title")
    if work_title:
        source_info += f" {work_title}"
    if chunk.metadata.get("unit_number"):
        source_info += f" - ماده {chunk.metadata['unit_number']}"
    
    context_parts.append(f"{source_info}:\n{chunk.text}")

context = "\n\n".join(context_parts)
```

**مثال Context:**
```
[منبع 1] قانون چلمنگان - ماده 10:
متن کامل ماده 10...

[منبع 2] قانون چلمنگان - ماده 11:
متن کامل ماده 11...

...
```

**ساخت System Prompt:**
```python
system_prompt = """شما یک دستیار حقوقی هوشمند هستید که به سوالات کسب و کار بر اساس قوانین و مقررات ایران پاسخ می‌دهید.

وظایف شما:
- پاسخ‌های دقیق و جامع بر اساس اطلاعات مرجع ارائه شده
- ارجاع به منابع و مواد قانونی مرتبط
- توضیح مفاهیم حقوقی به زبان ساده
- اشاره به نکات مهم و استثناها

محدودیت‌ها:
- فقط از اطلاعات مرجع ارائه شده استفاده کنید
- از اظهار نظر شخصی خودداری کنید
- اگر اطلاعات کافی ندارید، صراحتاً اعلام کنید"""
```

**ساخت User Message:**
```python
user_message = f"""سوال کاربر: {query.text}

اطلاعات مرجع:
{context}"""
```

**فراخوانی LLM:**
```python
messages = [
    Message(role="system", content=system_prompt),
    Message(role="user", content=user_message)
]

# استفاده از gpt-4o-mini
response = await self.llm.generate(messages)
```

#### فایل: `/srv/app/llm/openai_provider.py` - متد `generate()` (خط 52-99)

**پارامترهای API Call:**
```python
params = {
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    "max_tokens": 4096,
    "temperature": 0.4,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0
}

response = await self.client.chat.completions.create(**params)
```

**پاسخ LLM:**
```python
LLMResponse(
    content="طبق ماده 10 قانون چلمنگان، ...",
    model="gpt-4o-mini",
    usage={
        "prompt_tokens": 1250,
        "completion_tokens": 320,
        "total_tokens": 1570
    },
    finish_reason="stop"
)
```

---

### 🔹 Step 7: استخراج منابع (خط 176-177)

```python
sources = self._extract_sources(chunks)
```

#### فایل: `/srv/app/rag/pipeline.py` - متد `_extract_sources()` (خط 588-658)

**فرمت منابع:**
```python
sources = []
for i, chunk in enumerate(chunks, 1):
    source_lines = [
        f"📌 منبع {i}:",
        f"📄 متن: {chunk.text}",
        "",
        f"📕 نام سند: {work_title}",
        f"📍 مسیر: {path_label}",
        f"✅ مرجع تصویب: {authority}"  # فقط برای غیر قوانین
    ]
    sources.append("\n".join(source_lines))
```

**مثال خروجی:**
```
📌 منبع 1:
📄 متن: ماده 10 - هر کس...
📕 نام سند: قانون چلمنگان
📍 مسیر: فصل 2 > بخش 1 > ماده 10

📌 منبع 2:
...
```

---

### 🔹 Step 8: ساخت Response و Cache (خط 179-196)

```python
response = RAGResponse(
    answer=answer,
    chunks=chunks,
    sources=sources,
    total_tokens=tokens_used,
    processing_time_ms=processing_time,
    model_used=self.llm.config.model
)

if query.use_cache:
    await self._cache_response(query, response)

return response
```

---

## 📍 مرحله 3: ذخیره در Database و ارسال به کاربر

### فایل: `/srv/app/api/v1/endpoints/query.py` (خط 290-361)

**ذخیره پیام‌ها:**
```python
# پیام کاربر
user_message = DBMessage(
    id=uuid.uuid4(),
    conversation_id=conversation.id,
    role=MessageRole.USER,
    content=request.query,
    created_at=datetime.utcnow()
)
db.add(user_message)

# پیام دستیار
assistant_message = DBMessage(
    id=uuid.uuid4(),
    conversation_id=conversation.id,
    role=MessageRole.ASSISTANT,
    content=rag_response.answer,
    tokens=rag_response.total_tokens,
    processing_time_ms=rag_response.processing_time_ms,
    retrieved_chunks=[...],  # ذخیره chunks برای debug
    sources=rag_response.sources,
    model_used=rag_response.model_used,
    created_at=datetime.utcnow()
)
db.add(assistant_message)
```

**به‌روزرسانی آمار:**
```python
conversation.message_count += 2
conversation.total_tokens += rag_response.total_tokens
user.increment_query_count()
user.total_tokens_used += rag_response.total_tokens

await db.commit()
```

**ارسال به سیستم کاربران (Background Task):**
```python
from app.tasks.notifications import send_query_result_to_users

send_query_result_to_users.delay(
    user_id=str(user.id),
    conversation_id=str(conversation.id),
    message_id=str(assistant_message.id),
    query=request.query,
    answer=rag_response.answer,
    sources=rag_response.sources,
    tokens_used=rag_response.total_tokens,
    processing_time_ms=rag_response.processing_time_ms
)
```

**پاسخ نهایی به API:**
```python
return QueryResponse(
    answer=rag_response.answer,
    sources=rag_response.sources,
    conversation_id=str(conversation.id),
    message_id=str(assistant_message.id),
    tokens_used=rag_response.total_tokens,
    processing_time_ms=rag_response.processing_time_ms,
    cached=rag_response.cached
)
```

---

## 📊 خلاصه فراخوانی‌های LLM

| مرحله | فایل | متد | Prompt | Temperature | Max Tokens | هدف |
|-------|------|-----|--------|-------------|------------|-----|
| **1. Classification** | `llm/classifier.py` | `classify()` | دسته‌بندی سوال | 0.2 | 512 | تشخیص نوع سوال |
| **2. Query Enhancement** | `rag/pipeline.py` | `_enhance_query()` | بهبود query | 0.1 | 200 | نرمال‌سازی و بهبود |
| **3. Answer Generation** | `rag/pipeline.py` | `_generate_answer()` | تولید پاسخ با context | 0.4 | 4096 | پاسخ نهایی |

---

## 🎯 نمودار جریان کامل

```
1. API Request
   ↓
2. Authentication & User Check
   ↓
3. LLM Classification (business_question?)
   ↓ YES
4. Cache Check
   ↓ MISS
5. LLM Query Enhancement ("ماده ده" → "ماده 10")
   ↓
6. Generate Embedding (1024 dims)
   ↓
7. Qdrant Vector Search (score_threshold=0.4)
   ↓
8. Retrieve 15 chunks
   ↓
9. Rerank to top 5
   ↓
10. Build Context from chunks
   ↓
11. LLM Answer Generation (with context)
   ↓
12. Extract Sources
   ↓
13. Save to Database
   ↓
14. Send to Users System (Celery)
   ↓
15. Return Response
```

---

## ⚡ نکات کلیدی

1. **3 بار LLM فراخوانی می‌شود**: Classification → Enhancement → Generation
2. **Qdrant فقط یک بار**: Vector search با threshold=0.4
3. **Reranking فعلاً غیرفعال**: چون Cohere API key خالی است
4. **Cache در Redis**: برای سرعت بخشیدن به queries تکراری
5. **Background tasks**: ارسال نتیجه به Users system بدون تأخیر در response

---

## 🔧 تغییرات اخیر برای رفع مشکل RAG

### 1. رفع مشکل Hybrid Search
- حذف keyword search نادرست که فقط exact match را پشتیبانی می‌کرد
- استفاده از vector search خالص با threshold=0.4

### 2. کاهش Similarity Threshold
- تغییر از 0.7 به 0.5 برای افزایش recall

### 3. بهبود Query Enhancement
- تغییر از hardcoded replacements به LLM-based enhancement
- پشتیبانی از تمام اختصارات، تصحیح املا، و نرمال‌سازی هوشمند

### 4. افزودن لاگ‌های Debug
- لاگ تعداد و امتیاز chunks بازیابی شده
- لاگ نام اسناد و منابع
- لاگ query enhancement

---

## 📝 فایل‌های کلیدی

| فایل | نقش |
|------|-----|
| `/srv/app/api/v1/endpoints/query.py` | نقطه ورود API |
| `/srv/app/rag/pipeline.py` | هسته اصلی RAG pipeline |
| `/srv/app/llm/classifier.py` | دسته‌بندی سوالات |
| `/srv/app/llm/openai_provider.py` | ارتباط با OpenAI API |
| `/srv/app/services/qdrant_service.py` | جستجو در vector database |
| `/srv/app/services/embedding_service.py` | تولید embeddings |
| `/srv/.env` | تنظیمات (thresholds, API keys) |
