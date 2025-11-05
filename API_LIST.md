# 📋 لیست کامل API های Core System

**تاریخ:** 2024-11-05  
**Base URL:** `https://core.arpanet.ir`

---

## 🏠 Root Endpoints (عمومی)

| Method | Endpoint | توضیح | Authentication |
|--------|----------|-------|----------------|
| GET | `/` | صفحه اصلی | ❌ |
| GET | `/health` | Health check کامل (PostgreSQL, Redis, Qdrant) | ❌ |
| GET | `/report` | گزارش آمار Qdrant (تعداد نودها) | ❌ |
| GET | `/metrics` | Prometheus metrics | ❌ |
| GET | `/docs` | Swagger UI (فقط dev) | ❌ |
| GET | `/redoc` | ReDoc (فقط dev) | ❌ |

---

## 🔍 Query API - `/api/v1/query`

**هدف:** پردازش سوالات و RAG

| Method | Endpoint | توضیح | Authentication |
|--------|----------|-------|----------------|
| POST | `/api/v1/query/` | پردازش سوال (RAG) | ❌ |
| POST | `/api/v1/query/stream` | پردازش سوال (streaming) | ❌ |
| POST | `/api/v1/query/feedback` | ارسال بازخورد | ❌ |

### نمونه Request:
```json
POST /api/v1/query/
{
  "query": "قانون حمایت از حقوق مصرف‌کنندگان چیست؟",
  "user_id": "user-123",
  "conversation_id": "conv-456",
  "filters": {
    "document_type": "LAW"
  }
}
```

---

## 🔄 Sync API - `/api/v1/sync`

**هدف:** همگام‌سازی با سیستم Ingest  
**Authentication:** ✅ API Key required (`X-API-Key` header)

| Method | Endpoint | توضیح | Request | Response |
|--------|----------|-------|---------|----------|
| POST | `/api/v1/sync/embeddings` | ارسال embeddings از Ingest | `SyncEmbeddingsRequest` | `{status, synced_count, node_ids}` |
| GET | `/api/v1/sync/node/{node_id}` | اطلاعات کامل یک نود | - | `NodeDetailResponse` |
| GET | `/api/v1/sync/statistics` | آمار کامل Core | - | `SyncStatisticsResponse` |
| GET | `/api/v1/sync/status` | وضعیت sync | - | `SyncStatusResponse` |
| POST | `/api/v1/sync/trigger-full-sync` | شروع sync کامل | - | `{status, message}` |
| POST | `/api/v1/sync/process-queue` | پردازش صف sync | - | `{status, processed}` |
| DELETE | `/api/v1/sync/document/{doc_id}` | حذف embeddings یک سند | - | `{status, deleted_count}` |

### نمونه Request - ارسال Embeddings:
```json
POST /api/v1/sync/embeddings
Header: X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/

{
  "embeddings": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "vector": [0.123, -0.456, ...],
      "text": "ماده ۱ - این قانون...",
      "document_id": "doc-12345",
      "metadata": {
        "work_title": "قانون حمایت از حقوق مصرف‌کنندگان",
        "doc_type": "LAW",
        "language": "fa"
      }
    }
  ],
  "sync_type": "incremental"
}
```

### Response:
```json
{
  "status": "success",
  "synced_count": 1,
  "node_ids": [
    "550e8400-e29b-41d4-a716-446655440000"
  ],
  "timestamp": "2024-11-05T10:30:00.000000"
}
```

### نمونه Request - دریافت اطلاعات نود:
```bash
GET /api/v1/sync/node/550e8400-e29b-41d4-a716-446655440000
Header: X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/
```

### Response - اطلاعات کامل نود:
```json
{
  "node_id": "550e8400-e29b-41d4-a716-446655440000",
  "exists": true,
  "vector": [0.123, -0.456, 0.789, ...],
  "text": "ماده ۱ - این قانون به منظور حمایت از حقوق مصرف‌کنندگان...",
  "document_id": "doc-12345",
  "document_type": "LAW",
  "chunk_index": 0,
  "language": "fa",
  "source": "ingest",
  "metadata": {
    "work_title": "قانون حمایت از حقوق مصرف‌کنندگان",
    "doc_type": "LAW",
    "authority": "مجلس شورای اسلامی",
    "approval_date": "1388/12/15",
    "jurisdiction": "IR"
  },
  "created_at": "2024-11-05T04:30:00.000000",
  "updated_at": "2024-11-05T04:30:00.000000",
  "vector_dimensions": {
    "medium": 768,
    "default": 3072
  }
}
```

---

## 🧮 Embedding API - `/api/v1/embeddings`

**هدف:** تولید embedding و محاسبه similarity

| Method | Endpoint | توضیح | Authentication |
|--------|----------|-------|----------------|
| POST | `/api/v1/embeddings/embeddings` | تولید embedding | ❌ |
| GET | `/api/v1/embeddings/info` | اطلاعات سرویس embedding | ❌ |
| POST | `/api/v1/embeddings/similarity` | محاسبه similarity | ❌ |

### نمونه:
```json
POST /api/v1/embeddings/embeddings
{
  "input": ["متن اول", "متن دوم"],
  "model": "intfloat/multilingual-e5-base"
}
```

---

## 👤 Users API - `/api/v1/users`

**هدف:** مدیریت کاربران و مکالمات  
**Authentication:** ✅ JWT Token required

| Method | Endpoint | توضیح |
|--------|----------|-------|
| GET | `/api/v1/users/profile` | پروفایل کاربر |
| PATCH | `/api/v1/users/profile` | به‌روزرسانی پروفایل |
| GET | `/api/v1/users/conversations` | لیست مکالمات |
| GET | `/api/v1/users/conversations/{id}/messages` | پیام‌های یک مکالمه |
| DELETE | `/api/v1/users/conversations/{id}` | حذف مکالمه |
| GET | `/api/v1/users/statistics` | آمار کاربر |
| POST | `/api/v1/users/clear-history` | پاک کردن تاریخچه |

---

## 🔧 Admin API - `/api/v1/admin`

**هدف:** مدیریت سیستم  
**Authentication:** ✅ Admin Access required

| Method | Endpoint | توضیح |
|--------|----------|-------|
| GET | `/api/v1/admin/stats` | آمار سیستم |
| GET | `/api/v1/admin/cache/stats` | آمار cache |
| POST | `/api/v1/admin/cache/clear` | پاک کردن cache |
| GET | `/api/v1/admin/users` | لیست کاربران |
| PATCH | `/api/v1/admin/users/{id}/tier` | تغییر tier کاربر |
| POST | `/api/v1/admin/qdrant/optimize` | بهینه‌سازی Qdrant |
| GET | `/api/v1/admin/health/detailed` | Health check دقیق |

---

## 🏥 Health API - `/api/v1/health`

**هدف:** Health checks برای Kubernetes

| Method | Endpoint | توضیح |
|--------|----------|-------|
| GET | `/api/v1/health/` | Health check ساده |
| GET | `/api/v1/health/ready` | Readiness check |
| GET | `/api/v1/health/live` | Liveness check |

---

## 🔐 Authentication

### 1. API Key (برای Sync API):
```bash
Header: X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/
```

### 2. JWT Token (برای Users API):
```bash
Header: Authorization: Bearer <jwt_token>
```

### 3. Admin Access (برای Admin API):
```bash
Header: X-Admin-Key: <admin_key>
```

---

## 📊 Response Models

### NodeDetailResponse (کامل):
```typescript
{
  node_id: string,           // UUID اصلی
  exists: boolean,           // آیا نود موجود است؟
  vector: float[],           // بردار اصلی (768 یا 3072 بعدی)
  text: string,              // متن کامل
  document_id: string,       // شناسه سند
  document_type: string,     // نوع سند (LAW, REGULATION, ...)
  chunk_index: number,       // شماره chunk
  language: string,          // زبان (fa, en, ...)
  source: string,            // منبع (ingest, manual, ...)
  metadata: object,          // متادیتای کامل
  created_at: string,        // زمان ایجاد (ISO 8601)
  updated_at: string,        // زمان آخرین بروزرسانی
  vector_dimensions: {       // ابعاد بردارهای موجود
    medium: 768,
    default: 3072
  }
}
```

### SyncStatisticsResponse:
```typescript
{
  timestamp: string,
  postgresql: {
    users: {...},
    conversations: {...},
    messages: {...},
    cache: {...},
    feedback: {...}
  },
  qdrant: {
    collection_name: string,
    points_count: number,
    vectors_count: number,
    indexed_vectors_count: number,
    status: string
  },
  summary: {
    total_users: number,
    total_conversations: number,
    total_messages: number,
    total_vectors: number
  }
}
```

---

## 🧪 نمونه استفاده

### Python:
```python
import requests

# ارسال embedding
response = requests.post(
    "https://core.arpanet.ir/api/v1/sync/embeddings",
    json={"embeddings": [...]},
    headers={"X-API-Key": "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"}
)

# دریافت اطلاعات نود
node_data = requests.get(
    "https://core.arpanet.ir/api/v1/sync/node/550e8400-...",
    headers={"X-API-Key": "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"}
).json()

print(f"Text: {node_data['text']}")
print(f"Type: {node_data['document_type']}")
print(f"Language: {node_data['language']}")
```

### cURL:
```bash
# Health check
curl https://core.arpanet.ir/health

# دریافت اطلاعات نود
curl "https://core.arpanet.ir/api/v1/sync/node/550e8400-..." \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
```

---

## 📝 نکات مهم

1. ✅ **Endpoint نود اطلاعات کامل برمی‌گرداند** شامل:
   - بردار کامل
   - متن
   - document_type
   - chunk_index
   - language
   - source
   - metadata کامل
   - timestamps

2. ✅ **API Key** برای تمام Sync endpoints الزامی است

3. ✅ **Rate Limiting:** حداکثر 100 request/second

4. ✅ **Timeout:** 60 ثانیه برای تمام endpoints

---

**آخرین به‌روزرسانی:** 2024-11-05 10:30 UTC
