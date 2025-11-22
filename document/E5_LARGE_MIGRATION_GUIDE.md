# راهنمای مهاجرت به مدل e5-large (768d → 1024d)

## نمای کلی

این سند راهنمای کامل مهاجرت از مدل `multilingual-e5-base` (768 بعد) به `multilingual-e5-large` (1024 بعد) را ارائه می‌دهد.

## تغییرات اعمال شده در Core System

### 1. تنظیمات Qdrant Collection

**قبل:**
```python
"large": VectorParams(
    size=1536,  # OpenAI ada-002
    distance=Distance.COSINE,
)
```

**بعد:**
```python
"large": VectorParams(
    size=1024,  # e5-large, bge-m3
    distance=Distance.COSINE,
),
"xlarge": VectorParams(
    size=1536,  # OpenAI ada-002, text-embedding-3-small
    distance=Distance.COSINE,
)
```

### 2. Vector Field Mapping Logic

**قبل:**
```python
def _get_vector_field_by_dim(self, dim: int) -> str:
    if dim <= 512:
        return "small"
    elif dim <= 768:
        return "medium"
    elif dim <= 1536:
        return "large"
    else:
        return "default"
```

**بعد:**
```python
def _get_vector_field_by_dim(self, dim: int) -> str:
    if dim <= 512:
        return "small"
    elif dim <= 768:
        return "medium"
    elif dim <= 1024:
        return "large"  # e5-large, bge-m3
    elif dim <= 1536:
        return "xlarge"  # OpenAI ada-002, text-embedding-3-small
    else:
        return "default"  # 3072
```

### 3. فایل‌های تغییر یافته

- ✅ `/srv/app/services/qdrant_service.py` - تنظیمات collection
- ✅ `/srv/app/services/sync_service.py` - mapping logic
- ✅ `/srv/app/rag/pipeline.py` - mapping logic
- ✅ `/srv/document/2_INGEST_SYSTEM_API_GUIDE.md` - مستندات
- ✅ `/srv/document/EMBEDDING_CONFIGURATION_GUIDE.md` - مستندات

## مراحل مهاجرت

### مرحله 1: پاک کردن Qdrant Collection (Core System)

```bash
# اجرای اسکریپت reset
cd /srv
python scripts/reset_qdrant_collection.py
```

این اسکریپت:
- ✅ تمام نودهای Qdrant را حذف می‌کند
- ✅ Collection را با تنظیمات جدید دوباره می‌سازد
- ✅ از شما تایید می‌گیرد قبل از حذف

**خروجی مورد انتظار:**
```
======================================================================
Qdrant Collection Reset Script
======================================================================

⚠️  WARNING: This will DELETE ALL vectors in Qdrant!
   Collection: legal_documents
   Host: localhost:7333

Are you sure you want to continue? (yes/no): yes

Initializing Qdrant service...
📊 Checking current collection status...
   Current points count: 15000
   Current vectors count: 15000
   Current status: green

🗑️  Deleting collection...
✅ Collection deleted successfully!

🔨 Creating new collection with updated configuration...
   Supported dimensions:
      - small: 512
      - medium: 768
      - large: 1024  ← e5-large
      - xlarge: 1536
      - default: 3072
✅ Collection created successfully!

📊 New collection info:
   Status: green
   Points count: 0

======================================================================
✅ Qdrant collection reset completed successfully!
======================================================================

Next steps:
1. Make sure the ingest system is configured with e5-large model
2. Re-embed all chunks in the ingest system
3. Sync all embeddings to Core using: POST /api/v1/sync/embeddings
```

### مرحله 2: تنظیم Ingest System

#### 2.1 تغییر مدل Embedding

در فایل `.env` سیستم Ingest:

```bash
# قبل
EMBEDDING_MODEL="intfloat/multilingual-e5-base"
EMBEDDING_DIM=768

# بعد
EMBEDDING_MODEL="intfloat/multilingual-e5-large"
EMBEDDING_DIM=1024
```

#### 2.2 Re-embed همه Chunks

```bash
# در سیستم Ingest
python manage.py re_embed_all_chunks --model intfloat/multilingual-e5-large
```

این دستور:
- تمام chunks موجود را با مدل جدید re-embed می‌کند
- dimension را از 768 به 1024 تغییر می‌دهد
- در دیتابیس Ingest ذخیره می‌کند

### مرحله 3: همگام‌سازی با Core

#### 3.1 Full Sync

```bash
# در سیستم Ingest
python manage.py sync_to_core --full --batch-size 100
```

#### 3.2 تایید همگام‌سازی

```bash
# بررسی وضعیت
curl -X GET http://core-api:7001/api/v1/sync/status \
  -H "X-API-Key: ${INGEST_API_KEY}"
```

**خروجی مورد انتظار:**
```json
{
  "last_sync": "2025-11-22T04:56:00Z",
  "pending_count": 0,
  "synced_count": 15000,
  "error_count": 0,
  "qdrant_status": {
    "total_points": 15000,
    "indexed_vectors": 15000,
    "status": "healthy"
  }
}
```

## تایید نهایی

### 1. بررسی Qdrant Collection

```bash
# در Core system
python3 << EOF
from app.services.qdrant_service import QdrantService
qdrant = QdrantService()
info = qdrant.client.get_collection("legal_documents")
print(f"Points: {info.points_count}")
print(f"Vectors: {info.vectors_count}")
print(f"Status: {info.status}")
EOF
```

### 2. تست جستجو

```bash
curl -X POST http://core-api:7001/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "query": "تست سیستم",
    "limit": 5
  }'
```

### 3. بررسی Vector Field

```bash
# دریافت یک نمونه node
curl -X GET http://core-api:7001/api/v1/sync/node/953652110735163 \
  -H "X-API-Key: ${INGEST_API_KEY}"
```

**خروجی مورد انتظار:**
```json
{
  "status": "success",
  "node": {
    "id": "953652110735163",
    "vectors": {
      "large": [0.1, 0.2, ...]  // 1024 dimensions
    }
  }
}
```

## Troubleshooting

### مشکل 1: Dimension Mismatch

**خطا:**
```
Expected vector dimension 1024 but got 768
```

**راه‌حل:**
- مطمئن شوید که Ingest system با مدل e5-large re-embed کرده است
- بررسی کنید که `EMBEDDING_DIM=1024` در Ingest تنظیم شده باشد

### مشکل 2: Vector Field Incorrect

**خطا:**
```
Vector field 'medium' not found for 1024 dimensions
```

**راه‌حل:**
- Core system را restart کنید تا تغییرات اعمال شود
- مطمئن شوید که کد جدید deploy شده است

### مشکل 3: Sync Fails

**خطا:**
```
Failed to sync embeddings: 500 Internal Server Error
```

**راه‌حل:**
1. بررسی logs Core system:
   ```bash
   docker-compose logs core-api | tail -100
   ```
2. بررسی اتصال Qdrant:
   ```bash
   curl http://localhost:7333/collections/legal_documents
   ```

## Rollback Plan

اگر مشکلی پیش آمد:

### 1. بازگشت به e5-base

```bash
# در Ingest system
EMBEDDING_MODEL="intfloat/multilingual-e5-base"
EMBEDDING_DIM=768

# Re-embed و sync دوباره
python manage.py re_embed_all_chunks --model intfloat/multilingual-e5-base
python manage.py sync_to_core --full
```

### 2. Reset Qdrant برای 768 dimensions

```bash
# تغییر موقت کد برای 768d
# سپس اجرای reset script
python scripts/reset_qdrant_collection.py
```

## Performance Comparison

### e5-base (768d)
- **Embedding Speed**: ~200 docs/sec
- **Search Latency**: ~50ms
- **Model Size**: ~1GB
- **Quality**: خوب

### e5-large (1024d)
- **Embedding Speed**: ~150 docs/sec
- **Search Latency**: ~60ms
- **Model Size**: ~2GB
- **Quality**: عالی ⭐

## Best Practices

1. ✅ همیشه قبل از migration، backup از Qdrant بگیرید
2. ✅ Migration را در ساعات کم‌کاری انجام دهید
3. ✅ تمام مراحل را در محیط staging تست کنید
4. ✅ Monitoring را فعال نگه دارید
5. ✅ Rollback plan آماده داشته باشید

## Checklist

- [ ] Core system کد جدید را دارد
- [ ] Qdrant collection پاک شده است
- [ ] Ingest system با e5-large تنظیم شده
- [ ] همه chunks re-embed شده‌اند
- [ ] Full sync به Core انجام شده
- [ ] تست‌های جستجو موفق هستند
- [ ] Monitoring نشان می‌دهد همه چیز سالم است

## تماس و پشتیبانی

در صورت بروز مشکل، لاگ‌های زیر را بررسی کنید:
- Core API logs: `docker-compose logs core-api`
- Qdrant logs: `docker-compose logs qdrant`
- Ingest logs: `python manage.py check_logs`

---

**آخرین بروزرسانی:** 2025-11-22  
**نسخه:** 1.0  
**وضعیت:** آماده برای اجرا
