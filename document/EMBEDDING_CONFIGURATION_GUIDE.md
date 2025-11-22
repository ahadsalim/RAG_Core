# راهنمای پیکربندی Embedding در Core System

## نمای کلی

سیستم Core از یک **Unified Embedding Service** استفاده می‌کند که به صورت خودکار بین دو حالت تصمیم می‌گیرد:

1. **API Mode**: استفاده از API های خارجی (OpenAI, etc.)
2. **Local Mode**: استفاده از مدل‌های محلی (sentence-transformers)

## تشخیص خودکار حالت

سیستم بر اساس تنظیمات `.env` به صورت خودکار حالت را انتخاب می‌کند:

```bash
# اگر EMBEDDING_API_KEY مقدار داشته باشد → API Mode
EMBEDDING_API_KEY="sk-..."
EMBEDDING_BASE_URL="https://api.openai.com/v1"
EMBEDDING_MODEL="text-embedding-3-large"

# اگر EMBEDDING_API_KEY خالی باشد → Local Mode
EMBEDDING_API_KEY=""
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="intfloat/multilingual-e5-base"
```

---

## حالت 1: API Mode (توصیه شده برای Production)

### مزایا:
- ✅ سرعت بالا
- ✅ کیفیت بهتر
- ✅ نیاز به منابع سرور کمتر
- ✅ مقیاس‌پذیری بالا

### معایب:
- ❌ هزینه API
- ❌ وابستگی به سرویس خارجی

### پیکربندی برای OpenAI:

```bash
# /srv/.env
EMBEDDING_API_KEY="sk-proj-..."
EMBEDDING_BASE_URL=""  # خالی = استفاده از OpenAI پیش‌فرض
EMBEDDING_MODEL="text-embedding-3-large"  # 3072 بُعد
# یا
EMBEDDING_MODEL="text-embedding-3-small"  # 1536 بُعد
```

### پیکربندی برای سرویس‌های دیگر:

#### Together.ai:
```bash
EMBEDDING_API_KEY="your-together-api-key"
EMBEDDING_BASE_URL="https://api.together.xyz/v1"
EMBEDDING_MODEL="togethercomputer/m2-bert-80M-8k-retrieval"
```

#### Voyage AI:
```bash
EMBEDDING_API_KEY="your-voyage-api-key"
EMBEDDING_BASE_URL="https://api.voyageai.com/v1"
EMBEDDING_MODEL="voyage-large-2"
```

---

## حالت 2: Local Mode (برای Development یا بدون API)

### مزایا:
- ✅ بدون هزینه
- ✅ کنترل کامل
- ✅ بدون وابستگی خارجی
- ✅ حریم خصوصی کامل

### معایب:
- ❌ نیاز به منابع سرور (RAM, CPU/GPU)
- ❌ سرعت کمتر
- ❌ دانلود مدل در اولین اجرا

### پیکربندی:

```bash
# /srv/.env
EMBEDDING_API_KEY=""  # خالی = Local Mode
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="intfloat/multilingual-e5-base"  # 768 بُعد
```

### مدل‌های پیشنهادی Local:

| مدل | بُعد | زبان | حجم | کاربرد |
|-----|------|------|------|--------|
| `intfloat/multilingual-e5-base` | 768 | چندزبانه | ~1GB | **توصیه شده** |
| `intfloat/multilingual-e5-large` | 1024 | چندزبانه | ~2GB | کیفیت بالاتر |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | چندزبانه | ~1GB | جایگزین |
| `BAAI/bge-m3` | 1024 | چندزبانه | ~2GB | جدید و قدرتمند |

---

## ⚠️ هشدار مهم: تغییر مدل Embedding

### اگر مدل embedding را تغییر دهید، **حتماً** این مراحل را انجام دهید:

#### مرحله 1: پاک کردن Qdrant Collection
```bash
# وارد کانتینر Core شوید
docker exec -it core-api bash

# اجرای Python
python3

# پاک کردن collection
from app.services.qdrant_service import QdrantService
qdrant = QdrantService()
qdrant.client.delete_collection("legal_docs")
qdrant.ensure_collection()  # ایجاد مجدد با تنظیمات جدید
```

#### مرحله 2: Re-embed در سیستم Ingest
```bash
# در سیستم Ingest:
# 1. تنظیم مدل جدید در .env
# 2. اجرای دوباره embedding برای همه chunks

# مثال:
python manage.py re_embed_all_chunks
```

#### مرحله 3: Re-sync به Core
```bash
# در سیستم Ingest:
# ارسال دوباره همه embeddings به Core

python manage.py sync_to_core --full
```

---

## بررسی وضعیت Embedding Service

### از طریق Logs:

```bash
docker-compose logs core-api | grep -i embedding
```

**خروجی در API Mode:**
```
Embedding service initialized in API mode
model=text-embedding-3-large
base_url=https://api.openai.com/v1
```

**خروجی در Local Mode:**
```
⚠️  Embedding service initialized in LOCAL mode
model=intfloat/multilingual-e5-base
dimension=768
message=IMPORTANT: If you change embedding model, you MUST re-embed all chunks!
```

### از طریق API:

```bash
# تست embedding endpoint
curl -X POST http://localhost:7001/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "تست سیستم embedding"
  }'
```

---

## Vector Field در Qdrant

بسته به dimension مدل، از vector field مناسب استفاده شود:

| Dimension | Vector Field | مدل‌های نمونه |
|-----------|--------------|---------------|
| 512 | `small` | مدل‌های کوچک |
| 768 | `medium` | multilingual-e5-base, BERT |
| 1024 | `large` | **e5-large**, bge-m3 |
| 1536 | `xlarge` | text-embedding-3-small, ada-002 |
| 3072 | `default` | text-embedding-3-large |

### تنظیم در Sync:

```python
# در Ingest system هنگام ارسال به Core:
{
  "embeddings": [{
    "vector": [...],  # 1024 dimension (e5-large)
    "vector_field": "large",  # مطابق با dimension
    ...
  }]
}
```

---

## Performance Considerations

### API Mode:
- **Throughput**: ~1000 embeddings/min
- **Latency**: ~100-500ms per request
- **Cost**: $0.13 per 1M tokens (text-embedding-3-large)

### Local Mode:
- **Throughput**: ~50-200 embeddings/min (CPU), ~500-1000 (GPU)
- **Latency**: ~50-200ms per embedding (CPU), ~10-50ms (GPU)
- **RAM**: 2-4GB برای مدل
- **Cost**: رایگان

### توصیه:
- **Development**: Local Mode
- **Production با حجم کم**: Local Mode با GPU
- **Production با حجم بالا**: API Mode

---

## Troubleshooting

### مشکل 1: "Module not found: sentence_transformers"
```bash
# نصب در کانتینر
docker exec core-api pip install sentence-transformers torch
```

### مشکل 2: "Out of memory" در Local Mode
```bash
# کاهش batch size یا استفاده از مدل کوچکتر
EMBEDDING_MODEL="intfloat/multilingual-e5-small"  # 384 dimension
```

### مشکل 3: "API key invalid" در API Mode
```bash
# بررسی API key در .env
# مطمئن شوید که فاصله یا کاراکتر اضافی ندارد
EMBEDDING_API_KEY="sk-proj-..."  # بدون فاصله
```

### مشکل 4: Dimension mismatch
```bash
# خطا: Expected 768 but got 1536
# راه‌حل: تغییر vector_field یا re-embed با مدل صحیح
```

---

## Migration Guide

### از Local به API:

1. تنظیم API key در `.env`:
   ```bash
   EMBEDDING_API_KEY="sk-..."
   EMBEDDING_MODEL="text-embedding-3-large"
   ```

2. Restart سرویس:
   ```bash
   docker-compose restart core-api
   ```

3. Re-embed و re-sync (اگر dimension تغییر کرد)

### از API به Local:

1. خالی کردن API key:
   ```bash
   EMBEDDING_API_KEY=""
   EMBEDDING_MODEL="intfloat/multilingual-e5-base"
   ```

2. Restart و منتظر دانلود مدل بمانید:
   ```bash
   docker-compose restart core-api
   # اولین بار ~1-2GB دانلود می‌شود
   ```

3. Re-embed و re-sync (اگر dimension تغییر کرد)

---

## Best Practices

1. ✅ **همیشه** قبل از تغییر مدل، backup از Qdrant بگیرید
2. ✅ مدل embedding را در `.env` مستند کنید
3. ✅ در Production از API Mode استفاده کنید
4. ✅ Dimension را با vector_field مطابقت دهید
5. ✅ بعد از تغییر مدل، حتماً re-embed کنید
6. ❌ هرگز مدل را بدون re-embed تغییر ندهید
7. ❌ از مدل‌های مختلف برای Ingest و Core استفاده نکنید

---

## خلاصه تنظیمات توصیه شده

### برای شروع (Development):
```bash
EMBEDDING_API_KEY=""
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="intfloat/multilingual-e5-base"
```

### برای Production:
```bash
EMBEDDING_API_KEY="sk-proj-..."
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="text-embedding-3-large"
```

### برای Production با بودجه محدود:
```bash
EMBEDDING_API_KEY=""
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="intfloat/multilingual-e5-large"
# + استفاده از GPU
```
