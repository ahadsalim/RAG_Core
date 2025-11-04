# 📊 API آمار کامل Sync بین Ingest و Core

## 🎯 هدف
این API به شما امکان می‌دهد از سرور Ingest آمار کامل داده‌های منتقل شده و باقی‌مانده را دریافت کنید.

---

## 📍 Endpoint

```
GET /api/v1/sync/statistics
```

### Authentication
```
Header: X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/
```

---

## 🔧 نحوه فراخوانی

### از Ingest (Python):

```python
import requests

def get_sync_statistics():
    """دریافت آمار کامل sync از Core"""
    
    url = "https://core.arpanet.ir/api/v1/sync/statistics"
    # یا برای local: "http://localhost:7001/api/v1/sync/statistics"
    
    headers = {
        "X-API-Key": "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    return response.json()

# استفاده
stats = get_sync_statistics()

print(f"📊 آمار Sync:")
print(f"   تعداد در Ingest: {stats['summary']['total_embeddings_in_ingest']}")
print(f"   تعداد در Core: {stats['summary']['total_embeddings_in_core']}")
print(f"   منتقل شده: {stats['summary']['embeddings_transferred']}")
print(f"   باقی‌مانده: {stats['summary']['embeddings_remaining']}")
print(f"   درصد تکمیل: {stats['summary']['sync_completion']}")
```

### با curl:

```bash
curl -X GET "http://localhost:7001/api/v1/sync/statistics" \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  -H "Accept: application/json"
```

---

## 📥 نمونه Response

```json
{
  "timestamp": "2024-11-04T14:30:00.000000",
  
  "ingest_database": {
    "total_embeddings": 15000,
    "unique_documents": 3500,
    "by_dimension": {
      "512": 0,
      "768": 15000,
      "1536": 0,
      "3072": 0
    },
    "oldest_embedding": "2024-10-01T10:00:00",
    "newest_embedding": "2024-11-04T14:00:00",
    "sync_jobs": {
      "total": 250,
      "pending": 50,
      "running": 2,
      "success": 190,
      "error": 8,
      "by_type": {
        "documents": 200,
        "units": 40,
        "qa_pairs": 10
      }
    }
  },
  
  "core_qdrant": {
    "total_points": 12000,
    "vectors_count": 12000,
    "indexed_vectors": 12000,
    "status": "green",
    "collection_name": "legal_documents"
  },
  
  "sync_progress": {
    "last_sync": "2024-11-04T14:25:00.000000",
    "total_synced": 12000,
    "total_remaining": 3000,
    "sync_percentage": 80.0,
    "pending_jobs": 50,
    "error_jobs": 8
  },
  
  "summary": {
    "status": "pending",
    "total_embeddings_in_ingest": 15000,
    "total_embeddings_in_core": 12000,
    "embeddings_transferred": 12000,
    "embeddings_remaining": 3000,
    "sync_completion": "80.0%",
    "has_errors": true
  }
}
```

---

## 📊 توضیح فیلدها

### `ingest_database` - آمار دیتابیس Ingest

| فیلد | توضیح |
|------|-------|
| `total_embeddings` | تعداد کل embeddings در Ingest |
| `unique_documents` | تعداد اسناد یکتا |
| `by_dimension` | تفکیک بر اساس بعد بردار (512, 768, 1536, 3072) |
| `oldest_embedding` | قدیمی‌ترین embedding |
| `newest_embedding` | جدیدترین embedding |
| `sync_jobs.total` | تعداد کل job های sync |
| `sync_jobs.pending` | job های در انتظار |
| `sync_jobs.running` | job های در حال اجرا |
| `sync_jobs.success` | job های موفق |
| `sync_jobs.error` | job های با خطا |

### `core_qdrant` - آمار Qdrant در Core

| فیلد | توضیح |
|------|-------|
| `total_points` | تعداد کل نقاط در Qdrant |
| `vectors_count` | تعداد بردارها |
| `indexed_vectors` | تعداد بردارهای index شده |
| `status` | وضعیت collection (green/yellow/red) |
| `collection_name` | نام collection |

### `sync_progress` - پیشرفت Sync

| فیلد | توضیح |
|------|-------|
| `last_sync` | آخرین زمان sync |
| `total_synced` | تعداد کل منتقل شده |
| `total_remaining` | تعداد باقی‌مانده |
| `sync_percentage` | درصد تکمیل |
| `pending_jobs` | job های در انتظار |
| `error_jobs` | job های با خطا |

### `summary` - خلاصه

| فیلد | توضیح |
|------|-------|
| `status` | وضعیت کلی (synced/pending/error) |
| `total_embeddings_in_ingest` | کل در Ingest |
| `total_embeddings_in_core` | کل در Core |
| `embeddings_transferred` | تعداد منتقل شده |
| `embeddings_remaining` | تعداد باقی‌مانده |
| `sync_completion` | درصد تکمیل (رشته) |
| `has_errors` | آیا خطا وجود دارد؟ |

---

## 🐍 کلاس کامل Python برای Ingest

```python
import requests
from typing import Dict, Any
from datetime import datetime

class CoreSyncMonitor:
    """کلاس برای مانیتورینگ sync از Ingest"""
    
    def __init__(self, base_url: str = "https://core.arpanet.ir"):
        self.base_url = base_url
        self.api_key = "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
        self.headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """دریافت آمار کامل"""
        url = f"{self.base_url}/api/v1/sync/statistics"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def get_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه آمار"""
        stats = self.get_statistics()
        return stats["summary"]
    
    def get_remaining_count(self) -> int:
        """تعداد embeddings باقی‌مانده"""
        stats = self.get_statistics()
        return stats["summary"]["embeddings_remaining"]
    
    def get_sync_percentage(self) -> float:
        """درصد تکمیل sync"""
        stats = self.get_statistics()
        return stats["sync_progress"]["sync_percentage"]
    
    def is_fully_synced(self) -> bool:
        """آیا همه داده‌ها منتقل شده؟"""
        stats = self.get_statistics()
        return stats["summary"]["status"] == "synced"
    
    def has_errors(self) -> bool:
        """آیا خطا وجود دارد؟"""
        stats = self.get_statistics()
        return stats["summary"]["has_errors"]
    
    def print_report(self):
        """چاپ گزارش کامل"""
        stats = self.get_statistics()
        
        print("=" * 70)
        print("📊 گزارش Sync بین Ingest و Core")
        print("=" * 70)
        print(f"⏰ زمان: {stats['timestamp']}")
        print()
        
        print("📁 دیتابیس Ingest:")
        print(f"   • کل embeddings: {stats['ingest_database']['total_embeddings']:,}")
        print(f"   • اسناد یکتا: {stats['ingest_database']['unique_documents']:,}")
        print(f"   • بعد 768: {stats['ingest_database']['by_dimension']['768']:,}")
        print()
        
        print("🎯 Qdrant در Core:")
        print(f"   • کل points: {stats['core_qdrant']['total_points']:,}")
        print(f"   • وضعیت: {stats['core_qdrant']['status']}")
        print()
        
        print("📈 پیشرفت Sync:")
        print(f"   • منتقل شده: {stats['sync_progress']['total_synced']:,}")
        print(f"   • باقی‌مانده: {stats['sync_progress']['total_remaining']:,}")
        print(f"   • درصد تکمیل: {stats['sync_progress']['sync_percentage']}%")
        print(f"   • آخرین sync: {stats['sync_progress']['last_sync']}")
        print()
        
        print("✅ خلاصه:")
        print(f"   • وضعیت: {stats['summary']['status']}")
        print(f"   • تکمیل: {stats['summary']['sync_completion']}")
        print(f"   • خطا: {'بله ⚠️' if stats['summary']['has_errors'] else 'خیر ✅'}")
        print("=" * 70)


# استفاده
if __name__ == "__main__":
    monitor = CoreSyncMonitor()
    
    # چاپ گزارش کامل
    monitor.print_report()
    
    # یا استفاده از متدهای جداگانه
    remaining = monitor.get_remaining_count()
    print(f"\n📊 {remaining:,} embedding باقی‌مانده است")
    
    if monitor.is_fully_synced():
        print("✅ همه داده‌ها منتقل شده!")
    else:
        percentage = monitor.get_sync_percentage()
        print(f"⏳ {percentage:.1f}% تکمیل شده")
```

---

## 🧪 تست API

### تست ساده:
```bash
curl http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
```

### تست با jq (فرمت زیبا):
```bash
curl -s http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  | jq '.summary'
```

### تست فقط خلاصه:
```bash
curl -s http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  | jq '{
      total_in_ingest: .summary.total_embeddings_in_ingest,
      total_in_core: .summary.total_embeddings_in_core,
      remaining: .summary.embeddings_remaining,
      completion: .summary.sync_completion
    }'
```

---

## 🚨 خطاهای احتمالی

### 401 Unauthorized
```json
{
  "detail": "API key required"
}
```
**راه‌حل:** بررسی API Key در header

### 500 Internal Server Error
```json
{
  "detail": "Failed to get statistics: ..."
}
```
**راه‌حل:** بررسی اتصال به Ingest DB و Qdrant

### Connection Error
**راه‌حل:** بررسی که Core در حال اجرا باشد

---

## 📚 Endpoints مرتبط

| Endpoint | متد | توضیح |
|----------|-----|-------|
| `/api/v1/sync/statistics` | GET | آمار کامل (جدید) |
| `/api/v1/sync/status` | GET | وضعیت ساده |
| `/api/v1/sync/embeddings` | POST | ارسال embeddings |
| `/api/v1/sync/trigger-full-sync` | POST | شروع sync کامل |
| `/health` | GET | سلامت سیستم |

---

## ✅ نکات مهم

1. ✅ این API **read-only** است و تغییری ایجاد نمی‌کند
2. ✅ می‌توانید هر چند دقیقه یکبار فراخوانی کنید
3. ✅ آمار از **دو منبع** می‌آید:
   - دیتابیس Ingest (PostgreSQL)
   - Qdrant در Core
4. ✅ فیلد `embeddings_remaining` نشان می‌دهد چند داده باقی‌مانده
5. ✅ فیلد `sync_percentage` درصد تکمیل را نشان می‌دهد
6. ⚠️ اگر `has_errors: true` باشد، بعضی job ها با خطا مواجه شده‌اند

---

## 🎯 موارد استفاده

### 1. Dashboard در Ingest
```python
# هر 5 دقیقه آمار را بگیر و نمایش بده
import time

monitor = CoreSyncMonitor()

while True:
    stats = monitor.get_summary()
    print(f"Synced: {stats['embeddings_transferred']:,} / {stats['total_embeddings_in_ingest']:,}")
    print(f"Progress: {stats['sync_completion']}")
    time.sleep(300)  # 5 minutes
```

### 2. Alert اگر sync متوقف شد
```python
# چک کن اگر باقی‌مانده زیاد است
monitor = CoreSyncMonitor()
remaining = monitor.get_remaining_count()

if remaining > 1000:
    send_alert(f"⚠️ {remaining} embeddings are not synced yet!")
```

### 3. گزارش روزانه
```python
# ارسال گزارش روزانه
monitor = CoreSyncMonitor()
stats = monitor.get_statistics()

report = f"""
📊 گزارش روزانه Sync
━━━━━━━━━━━━━━━━━━━━━
✅ منتقل شده: {stats['summary']['embeddings_transferred']:,}
⏳ باقی‌مانده: {stats['summary']['embeddings_remaining']:,}
📈 پیشرفت: {stats['summary']['sync_completion']}
"""

send_email(report)
```

---

## 📖 مستندات کامل

مستندات تعاملی API:
```
http://localhost:7001/docs
```

در صفحه Swagger می‌توانید:
- API را تست کنید
- Schema کامل را ببینید
- نمونه‌های بیشتر ببینید

---

**تاریخ ایجاد:** 2024-11-04  
**نسخه API:** v1  
**وضعیت:** ✅ آماده استفاده
