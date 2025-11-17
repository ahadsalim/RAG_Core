# راهنمای فنی یکپارچه‌سازی زیرسیستم Ingest با Core System

## نمای کلی
زیرسیستم Ingest وظیفه جمع‌آوری، پردازش، و امبدینگ داده‌ها را دارد و آنها را برای سیستم Core آماده می‌کند. این سند راهنمای کامل فنی برای یکپارچه‌سازی Ingest با Core می‌باشد.

## معماری ارتباطی

```
┌─────────────────┐     API/Sync     ┌─────────────────┐
│                 │ ----------------> │                 │
│  Ingest System  │                   │   Core System   │
│                 │ <---------------- │                 │
└─────────────────┘     Webhooks     └─────────────────┘
```

## API Endpoints که Ingest باید فراخوانی کند

### 1. همگام‌سازی امبدینگ‌ها

#### Endpoint: `POST /api/v1/sync/embeddings`

**Headers:**
```json
{
  "X-API-Key": "{INGEST_API_KEY}",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "embeddings": [
    {
      "id": "953652110735163",  // شناسه یکتا (string)
      "vector": [0.1, 0.2, ...],  // بردار امبدینگ (768 بعد برای multilingual-e5-base)
      "text": "متن اصلی chunk",
      "document_id": "dee1acff-8131-49ec-b7ed-78d543dcc539",
      "metadata": {
        "language": "fa",
        "jurisdiction": "جمهوری اسلامی ایران",
        "doc_type": "legal",
        "category": "قانون مدنی",
        "section": "مالکیت",
        "article_number": 179,
        "date_issued": "1370-01-01",
        "authority": "مجلس شورای اسلامی",
        "keywords": ["مالکیت", "شکار", "تملک"],
        "chunk_index": 0,
        "total_chunks": 5,
        "source_page": 12,
        "confidence_score": 0.95
      }
    }
  ],
  "sync_type": "incremental"  // یا "full" برای همگام‌سازی کامل
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "synced_count": 1,
  "timestamp": "2025-11-17T06:00:00Z"
}
```

**Rate Limits:**
- Maximum batch size: 1000 embeddings per request
- Request rate: 60 requests/minute
- Daily limit: 100,000 embeddings

### 2. حذف داده‌های یک سند

#### Endpoint: `DELETE /api/v1/sync/document/{document_id}`

**Headers:**
```json
{
  "X-API-Key": "{INGEST_API_KEY}"
}
```

**Response:**
```json
{
  "status": "initiated",
  "message": "Document deletion started",
  "document_id": "dee1acff-8131-49ec-b7ed-78d543dcc539",
  "task_id": "celery-task-id-123"
}
```

### 3. بررسی وضعیت همگام‌سازی

#### Endpoint: `GET /api/v1/sync/status`

**Headers:**
```json
{
  "X-API-Key": "{INGEST_API_KEY}"
}
```

**Response:**
```json
{
  "last_sync": "2025-11-17T05:00:00Z",
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

### 4. دریافت آمار سیستم

#### Endpoint: `GET /api/v1/sync/statistics`

**Headers:**
```json
{
  "X-API-Key": "{INGEST_API_KEY}"
}
```

**Response:**
```json
{
  "status": "success",
  "timestamp": "2025-11-17T06:00:00Z",
  "environment": "production",
  "app_version": "1.0.0",
  "summary": {
    "total_users": 1500,
    "total_conversations": 8500,
    "total_messages": 45000,
    "total_vectors_in_qdrant": 150000
  },
  "postgresql": {
    "users": {"total": 1500},
    "conversations": {"total": 8500},
    "messages": {
      "total": 45000,
      "total_tokens": 2500000,
      "avg_processing_time_ms": 1200
    },
    "cache": {
      "total_cache_hits": 12000,
      "entries": 500
    }
  },
  "qdrant": {
    "total_points": 150000,
    "indexed_vectors": 150000,
    "status": "healthy",
    "collection_name": "legal_documents"
  },
  "core_db": {"status": "healthy"},
  "redis": {"status": "healthy"}
}
```

### 5. دریافت اطلاعات یک نقطه (Node)

#### Endpoint: `GET /api/v1/sync/node/{point_id}`

**Headers:**
```json
{
  "X-API-Key": "{INGEST_API_KEY}"
}
```

**Response:**
```json
{
  "status": "success",
  "node": {
    "id": "953652110735163",
    "payload": {
      "text": "متن کامل chunk",
      "document_id": "dee1acff-8131-49ec-b7ed-78d543dcc539",
      "document_type": "legal",
      "metadata": {...}
    },
    "vectors": {
      "medium": [0.1, 0.2, ...]  // 768 dimensions
    }
  }
}
```

## مدل‌های داده

### EmbeddingData Schema
```python
class EmbeddingData:
    id: str  # شناسه یکتا
    vector: List[float]  # بردار امبدینگ (768 بعد)
    text: str  # متن اصلی
    document_id: str  # شناسه سند
    metadata: Dict[str, Any]  # متادیتای اضافی
```

### Metadata Fields (پیشنهادی)
```python
metadata = {
    # فیلدهای اصلی
    "language": "fa",  # کد زبان ISO
    "doc_type": "legal|medical|educational|general",
    "category": str,  # دسته‌بندی سند
    
    # فیلدهای حقوقی (برای اسناد قانونی)
    "jurisdiction": str,  # حوزه قضایی
    "authority": str,  # مرجع صادرکننده
    "article_number": int,  # شماره ماده
    "section": str,  # بخش/فصل
    "date_issued": str,  # تاریخ صدور
    "date_effective": str,  # تاریخ اجرا
    
    # فیلدهای فنی
    "chunk_index": int,  # شماره chunk
    "total_chunks": int,  # تعداد کل chunks
    "source_page": int,  # شماره صفحه در سند اصلی
    "confidence_score": float,  # امتیاز اطمینان
    
    # فیلدهای جستجو
    "keywords": List[str],  # کلیدواژه‌ها
    "tags": List[str],  # برچسب‌ها
    
    # فیلدهای ردیابی
    "created_at": str,  # زمان ایجاد
    "updated_at": str,  # زمان آخرین بروزرسانی
    "source_system": str,  # سیستم منبع
    "processing_version": str  # ورژن پردازش
}
```

## الزامات امبدینگ

### 1. مدل پیشنهادی
```python
# استفاده از مدل multilingual-e5-base برای پشتیبانی از فارسی
model_name = "intfloat/multilingual-e5-base"
embedding_dim = 768  # ابعاد بردار

# نرمال‌سازی بردارها
normalized_vector = vector / np.linalg.norm(vector)
```

### 2. پیش‌پردازش متن
```python
def preprocess_text(text: str) -> str:
    # حذف فضای خالی اضافی
    text = " ".join(text.split())
    
    # حذف کاراکترهای کنترلی
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # نرمال‌سازی اعداد فارسی/عربی
    text = normalize_persian_numbers(text)
    
    # حداکثر طول: 512 توکن
    if len(text) > 2048:  # تقریبا 512 توکن
        text = text[:2048]
    
    return text
```

### 3. Chunking Strategy
```python
CHUNK_SIZE = 512  # کاراکتر
CHUNK_OVERLAP = 50  # کاراکتر همپوشانی

def create_chunks(text: str) -> List[Dict]:
    chunks = []
    for i in range(0, len(text), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk_text = text[i:i + CHUNK_SIZE]
        chunks.append({
            "text": chunk_text,
            "chunk_index": len(chunks),
            "start_char": i,
            "end_char": i + len(chunk_text)
        })
    return chunks
```

## Batch Processing Guidelines

### 1. Batch Sizes
```python
BATCH_CONFIG = {
    "embeddings_per_batch": 100,  # تعداد امبدینگ در هر batch
    "max_batch_size_mb": 10,  # حداکثر حجم batch
    "concurrent_batches": 5,  # تعداد batch های همزمان
    "retry_attempts": 3,  # تعداد تلاش مجدد
    "retry_delay_seconds": 5  # تاخیر بین تلاش‌ها
}
```

### 2. Error Handling
```python
async def sync_with_retry(embeddings: List[Dict]) -> bool:
    for attempt in range(BATCH_CONFIG["retry_attempts"]):
        try:
            response = await send_to_core(embeddings)
            if response.status_code == 200:
                return True
        except Exception as e:
            logger.error(f"Sync attempt {attempt + 1} failed: {e}")
            if attempt < BATCH_CONFIG["retry_attempts"] - 1:
                await asyncio.sleep(BATCH_CONFIG["retry_delay_seconds"])
    return False
```

## Sync Queue Implementation

### Database Schema (پیشنهادی برای Ingest)
```sql
CREATE TABLE sync_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    embedding_id VARCHAR(255) NOT NULL,
    vector VECTOR(768),
    text TEXT,
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    attempts INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sync_queue_status ON sync_queue(status);
CREATE INDEX idx_sync_queue_document ON sync_queue(document_id);
```

### Queue Processing Logic
```python
async def process_sync_queue():
    """پردازش صف همگام‌سازی"""
    while True:
        # دریافت آیتم‌های pending
        pending_items = await get_pending_items(limit=100)
        
        if not pending_items:
            await asyncio.sleep(10)  # صبر 10 ثانیه
            continue
        
        # تغییر وضعیت به processing
        await update_status(pending_items, "processing")
        
        # ارسال به Core
        try:
            await sync_to_core(pending_items)
            await update_status(pending_items, "completed")
        except Exception as e:
            await update_status(pending_items, "failed", error=str(e))
```

## Health Check & Monitoring

### 1. Health Check Endpoint (برای Ingest)
```python
@app.get("/health/core-connectivity")
async def check_core_connectivity():
    """بررسی ارتباط با Core"""
    try:
        response = requests.get(
            f"{CORE_URL}/api/v1/sync/status",
            headers={"X-API-Key": INGEST_API_KEY},
            timeout=5
        )
        return {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "core_reachable": response.status_code == 200,
            "response_time_ms": response.elapsed.total_seconds() * 1000
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "core_reachable": False,
            "error": str(e)
        }
```

### 2. Monitoring Metrics
```python
METRICS = {
    "embeddings_synced_total": Counter("embeddings_synced_total"),
    "sync_errors_total": Counter("sync_errors_total"),
    "sync_duration_seconds": Histogram("sync_duration_seconds"),
    "pending_queue_size": Gauge("pending_queue_size"),
}
```

## Security Requirements

### 1. API Key Management
```python
# .env file
INGEST_API_KEY=your-secure-api-key-min-32-chars

# استفاده در کد
headers = {
    "X-API-Key": os.getenv("INGEST_API_KEY"),
    "Content-Type": "application/json"
}
```

### 2. Rate Limiting
- استفاده از exponential backoff برای retry
- رعایت محدودیت‌های rate limit
- پیاده‌سازی circuit breaker برای جلوگیری از cascade failure

### 3. Data Validation
```python
def validate_embedding(embedding: Dict) -> bool:
    """اعتبارسنجی داده‌های امبدینگ"""
    # بررسی فیلدهای اجباری
    required_fields = ["id", "vector", "text", "document_id"]
    if not all(field in embedding for field in required_fields):
        return False
    
    # بررسی ابعاد بردار
    if len(embedding["vector"]) != 768:
        return False
    
    # بررسی محدوده مقادیر بردار
    if not all(-1 <= v <= 1 for v in embedding["vector"]):
        return False
    
    return True
```

## Best Practices

### 1. Logging
```python
logger.info("Syncing embeddings", extra={
    "batch_size": len(embeddings),
    "document_id": document_id,
    "sync_type": sync_type
})
```

### 2. Performance Optimization
- استفاده از connection pooling
- فشرده‌سازی داده‌ها برای انتقال (gzip)
- استفاده از async/await برای عملیات I/O

### 3. Error Recovery
- ذخیره embeddings در صف محلی قبل از ارسال
- پیاده‌سازی dead letter queue برای آیتم‌های failed
- نگهداری log از تمام عملیات sync

## نمونه کد کامل Integration

```python
import asyncio
import httpx
import numpy as np
from typing import List, Dict
import logging

class CoreSyncClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"X-API-Key": api_key},
            timeout=30.0
        )
    
    async def sync_embeddings(
        self, 
        embeddings: List[Dict],
        sync_type: str = "incremental"
    ) -> bool:
        """همگام‌سازی امبدینگ‌ها با Core"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/sync/embeddings",
                json={
                    "embeddings": embeddings,
                    "sync_type": sync_type
                }
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Sync failed: {e}")
            return False
    
    async def get_sync_status(self) -> Dict:
        """دریافت وضعیت همگام‌سازی"""
        response = await self.client.get(
            f"{self.base_url}/api/v1/sync/status"
        )
        return response.json()
    
    async def delete_document(self, document_id: str) -> bool:
        """حذف امبدینگ‌های یک سند"""
        response = await self.client.delete(
            f"{self.base_url}/api/v1/sync/document/{document_id}"
        )
        return response.status_code == 200

# استفاده
async def main():
    client = CoreSyncClient(
        base_url="https://core.yourdomain.com",
        api_key="your-api-key"
    )
    
    # آماده‌سازی embeddings
    embeddings = [
        {
            "id": "unique-id-123",
            "vector": np.random.randn(768).tolist(),
            "text": "متن نمونه",
            "document_id": "doc-456",
            "metadata": {
                "language": "fa",
                "category": "legal"
            }
        }
    ]
    
    # همگام‌سازی
    success = await client.sync_embeddings(embeddings)
    if success:
        print("Sync completed successfully")
    
    # بررسی وضعیت
    status = await client.get_sync_status()
    print(f"Synced vectors: {status['synced_count']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## تماس و پشتیبانی
در صورت نیاز به راهنمایی بیشتر یا بروز مشکل در یکپارچه‌سازی، با تیم Core تماس بگیرید.
