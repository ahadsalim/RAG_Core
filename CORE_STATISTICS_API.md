# 📊 API آمار کامل Core System

## 🎯 هدف
این API آمار کامل از **دیتابیس PostgreSQL** و **Qdrant** در پروژه Core را برمی‌گرداند.

---

## 📦 دیتابیس Core چه داده‌هایی دارد؟

### PostgreSQL (دیتابیس اصلی Core):
```
📁 جداول:
├── user_profiles          - پروفایل کاربران
├── conversations          - مکالمات (chat sessions)
├── messages              - پیام‌های داخل مکالمات
├── query_cache           - کش سوالات تکراری
└── user_feedback         - بازخورد کاربران
```

### Qdrant (Vector Database):
```
📁 Collection:
└── legal_documents       - بردارهای اسناد حقوقی
    ├── default (3072 dim)
    ├── large (1536 dim)
    ├── medium (768 dim)
    └── small (512 dim)
```

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

def get_core_statistics():
    """دریافت آمار کامل Core"""
    
    url = "https://core.arpanet.ir/api/v1/sync/statistics"
    # یا برای local: "http://localhost:7001/api/v1/sync/statistics"
    
    headers = {
        "X-API-Key": "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    return response.json()

# استفاده
stats = get_core_statistics()

print(f"📊 آمار Core:")
print(f"   کاربران: {stats['summary']['total_users']}")
print(f"   مکالمات: {stats['summary']['total_conversations']}")
print(f"   پیام‌ها: {stats['summary']['total_messages']}")
print(f"   بردارها در Qdrant: {stats['summary']['total_vectors_in_qdrant']}")
print(f"   میانگین رضایت: {stats['summary']['avg_user_rating']:.2f}/5")
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
  
  "postgresql": {
    "users": {
      "total": 1250,
      "by_tier": {
        "free": 1000,
        "basic": 150,
        "premium": 80,
        "enterprise": 20
      }
    },
    "conversations": {
      "total": 5600,
      "total_messages_in_conversations": 45000,
      "avg_messages_per_conversation": 8.04
    },
    "messages": {
      "total": 45000,
      "user_messages": 22500,
      "assistant_messages": 22500,
      "total_tokens": 15000000,
      "avg_processing_time_ms": 1250.5
    },
    "cache": {
      "total_cached_queries": 850,
      "total_cache_hits": 12500,
      "active_cache_entries": 650
    },
    "feedback": {
      "total": 3200,
      "avg_rating": 4.3,
      "processed": 2800
    }
  },
  
  "qdrant": {
    "total_points": 125000,
    "vectors_count": 125000,
    "indexed_vectors": 125000,
    "status": "green",
    "collection_name": "legal_documents"
  },
  
  "summary": {
    "total_users": 1250,
    "total_conversations": 5600,
    "total_messages": 45000,
    "total_vectors_in_qdrant": 125000,
    "total_cached_queries": 850,
    "avg_user_rating": 4.3,
    "qdrant_status": "green"
  }
}
```

---

## 📊 توضیح جداول PostgreSQL

### 1️⃣ `user_profiles` - پروفایل کاربران

| فیلد | توضیح |
|------|-------|
| `id` | UUID کاربر |
| `external_user_id` | شناسه کاربر از سیستم Users |
| `username` | نام کاربری |
| `email` | ایمیل |
| `tier` | سطح اشتراک (free/basic/premium/enterprise) |
| `daily_query_limit` | محدودیت سوال روزانه |
| `daily_query_count` | تعداد سوال امروز |
| `total_query_count` | تعداد کل سوالات |
| `preferences` | تنظیمات کاربر (JSON) |
| `last_active_at` | آخرین فعالیت |

### 2️⃣ `conversations` - مکالمات

| فیلد | توضیح |
|------|-------|
| `id` | UUID مکالمه |
| `user_id` | شناسه کاربر |
| `title` | عنوان مکالمه |
| `message_count` | تعداد پیام‌ها |
| `total_tokens` | تعداد کل توکن‌ها |
| `context` | زمینه مکالمه (JSON) |
| `llm_model` | مدل LLM استفاده شده |
| `last_message_at` | آخرین پیام |

### 3️⃣ `messages` - پیام‌ها

| فیلد | توضیح |
|------|-------|
| `id` | UUID پیام |
| `conversation_id` | شناسه مکالمه |
| `role` | نقش (user/assistant/system) |
| `content` | محتوای پیام |
| `tokens` | تعداد توکن‌ها |
| `processing_time_ms` | زمان پردازش (میلی‌ثانیه) |
| `retrieved_chunks` | چانک‌های بازیابی شده (JSON) |
| `sources` | منابع |
| `feedback_rating` | امتیاز (1-5) |
| `model_used` | مدل استفاده شده |

### 4️⃣ `query_cache` - کش سوالات

| فیلد | توضیح |
|------|-------|
| `id` | UUID |
| `query_hash` | هش سوال |
| `query_text` | متن سوال |
| `response` | پاسخ ذخیره شده |
| `hit_count` | تعداد استفاده |
| `last_hit_at` | آخرین استفاده |
| `expires_at` | زمان انقضا |

### 5️⃣ `user_feedback` - بازخورد کاربران

| فیلد | توضیح |
|------|-------|
| `id` | UUID |
| `user_id` | شناسه کاربر |
| `message_id` | شناسه پیام |
| `rating` | امتیاز (1-5) |
| `feedback_type` | نوع (accuracy/relevance/...) |
| `feedback_text` | متن بازخورد |
| `processed` | پردازش شده؟ |

---

## 📊 توضیح Qdrant

### Collection: `legal_documents`

**Vector Fields:**
- `default` (3072 dim) - OpenAI text-embedding-3-large
- `large` (1536 dim) - OpenAI ada-002
- `medium` (768 dim) - BERT-based models (e.g., multilingual-e5-base)
- `small` (512 dim) - Smaller models

**Payload Structure:**
```json
{
  "id": "uuid",
  "text": "متن کامل",
  "document_id": "doc-uuid",
  "metadata": {
    "work_title": "عنوان",
    "doc_type": "LAW/REGULATION/...",
    "language": "fa",
    ...
  }
}
```

---

## 🐍 کلاس کامل Python

```python
import requests
from typing import Dict, Any
from datetime import datetime

class CoreStatisticsMonitor:
    """کلاس برای مانیتورینگ آمار Core"""
    
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
    
    def get_user_count(self) -> int:
        """تعداد کاربران"""
        stats = self.get_statistics()
        return stats["postgresql"]["users"]["total"]
    
    def get_conversation_count(self) -> int:
        """تعداد مکالمات"""
        stats = self.get_statistics()
        return stats["postgresql"]["conversations"]["total"]
    
    def get_message_count(self) -> int:
        """تعداد پیام‌ها"""
        stats = self.get_statistics()
        return stats["postgresql"]["messages"]["total"]
    
    def get_vector_count(self) -> int:
        """تعداد بردارها در Qdrant"""
        stats = self.get_statistics()
        return stats["qdrant"]["total_points"]
    
    def get_avg_rating(self) -> float:
        """میانگین رضایت کاربران"""
        stats = self.get_statistics()
        return stats["postgresql"]["feedback"]["avg_rating"]
    
    def get_cache_hit_rate(self) -> float:
        """نرخ استفاده از کش"""
        stats = self.get_statistics()
        cache = stats["postgresql"]["cache"]
        if cache["total_cached_queries"] == 0:
            return 0.0
        return cache["total_cache_hits"] / cache["total_cached_queries"]
    
    def print_report(self):
        """چاپ گزارش کامل"""
        stats = self.get_statistics()
        
        print("=" * 70)
        print("📊 گزارش کامل Core System")
        print("=" * 70)
        print(f"⏰ زمان: {stats['timestamp']}")
        print()
        
        print("👥 کاربران:")
        users = stats['postgresql']['users']
        print(f"   • کل: {users['total']:,}")
        for tier, count in users['by_tier'].items():
            print(f"   • {tier}: {count:,}")
        print()
        
        print("💬 مکالمات:")
        conv = stats['postgresql']['conversations']
        print(f"   • کل مکالمات: {conv['total']:,}")
        print(f"   • کل پیام‌ها: {conv['total_messages_in_conversations']:,}")
        print(f"   • میانگین پیام/مکالمه: {conv['avg_messages_per_conversation']:.1f}")
        print()
        
        print("📝 پیام‌ها:")
        msg = stats['postgresql']['messages']
        print(f"   • کل: {msg['total']:,}")
        print(f"   • از کاربر: {msg['user_messages']:,}")
        print(f"   • از دستیار: {msg['assistant_messages']:,}")
        print(f"   • کل توکن‌ها: {msg['total_tokens']:,}")
        print(f"   • میانگین زمان پردازش: {msg['avg_processing_time_ms']:.1f}ms")
        print()
        
        print("💾 کش:")
        cache = stats['postgresql']['cache']
        print(f"   • کل کش شده: {cache['total_cached_queries']:,}")
        print(f"   • کل استفاده: {cache['total_cache_hits']:,}")
        print(f"   • فعال: {cache['active_cache_entries']:,}")
        hit_rate = self.get_cache_hit_rate()
        print(f"   • نرخ استفاده: {hit_rate:.1f}x")
        print()
        
        print("⭐ بازخورد:")
        feedback = stats['postgresql']['feedback']
        print(f"   • کل: {feedback['total']:,}")
        print(f"   • میانگین امتیاز: {feedback['avg_rating']:.2f}/5")
        print(f"   • پردازش شده: {feedback['processed']:,}")
        print()
        
        print("🎯 Qdrant:")
        qdrant = stats['qdrant']
        print(f"   • کل بردارها: {qdrant['total_points']:,}")
        print(f"   • Index شده: {qdrant['indexed_vectors']:,}")
        print(f"   • وضعیت: {qdrant['status']}")
        print(f"   • Collection: {qdrant['collection_name']}")
        print()
        
        print("✅ خلاصه:")
        summary = stats['summary']
        print(f"   • {summary['total_users']:,} کاربر")
        print(f"   • {summary['total_conversations']:,} مکالمه")
        print(f"   • {summary['total_messages']:,} پیام")
        print(f"   • {summary['total_vectors_in_qdrant']:,} بردار")
        print(f"   • رضایت: {summary['avg_user_rating']:.2f}/5 ⭐")
        print("=" * 70)


# استفاده
if __name__ == "__main__":
    monitor = CoreStatisticsMonitor()
    
    # چاپ گزارش کامل
    monitor.print_report()
    
    # یا استفاده از متدهای جداگانه
    print(f"\n📊 {monitor.get_user_count():,} کاربر فعال")
    print(f"💬 {monitor.get_conversation_count():,} مکالمه")
    print(f"🎯 {monitor.get_vector_count():,} بردار در Qdrant")
    print(f"⭐ میانگین رضایت: {monitor.get_avg_rating():.2f}/5")
```

---

## 🧪 تست API

### تست ساده:
```bash
curl http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
```

### تست با jq (فقط خلاصه):
```bash
curl -s http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  | jq '.summary'
```

### تست PostgreSQL:
```bash
curl -s http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  | jq '.postgresql'
```

### تست Qdrant:
```bash
curl -s http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/" \
  | jq '.qdrant'
```

---

## 📈 موارد استفاده

### 1. Dashboard در Ingest
```python
# نمایش آمار Core در dashboard
monitor = CoreStatisticsMonitor()
stats = monitor.get_statistics()

dashboard_data = {
    "users": stats['summary']['total_users'],
    "conversations": stats['summary']['total_conversations'],
    "vectors": stats['summary']['total_vectors_in_qdrant'],
    "satisfaction": stats['summary']['avg_user_rating']
}
```

### 2. Alert اگر Qdrant پر شد
```python
# چک کن اگر Qdrant بیش از 1 میلیون بردار دارد
monitor = CoreStatisticsMonitor()
vector_count = monitor.get_vector_count()

if vector_count > 1_000_000:
    send_alert(f"⚠️ Qdrant has {vector_count:,} vectors!")
```

### 3. گزارش عملکرد
```python
# گزارش روزانه عملکرد
monitor = CoreStatisticsMonitor()
stats = monitor.get_statistics()

report = f"""
📊 گزارش روزانه Core
━━━━━━━━━━━━━━━━━━━━━
👥 کاربران: {stats['summary']['total_users']:,}
💬 مکالمات: {stats['summary']['total_conversations']:,}
📝 پیام‌ها: {stats['summary']['total_messages']:,}
🎯 بردارها: {stats['summary']['total_vectors_in_qdrant']:,}
⭐ رضایت: {stats['summary']['avg_user_rating']:.2f}/5
"""

send_email(report)
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
**راه‌حل:** بررسی اتصال به PostgreSQL و Qdrant

---

## ✅ نکات مهم

1. ✅ این API **read-only** است
2. ✅ داده‌ها از **PostgreSQL Core** می‌آید (نه Ingest)
3. ✅ شامل آمار **Qdrant** هم هست
4. ✅ می‌توانید هر چند دقیقه یکبار فراخوانی کنید
5. ⚠️ اگر جدولی خالی باشد، مقدار 0 برمی‌گردد

---

## 📖 مستندات کامل

مستندات تعاملی API:
```
http://localhost:7001/docs
```

**تاریخ ایجاد:** 2024-11-04  
**نسخه API:** v1  
**وضعیت:** ✅ آماده استفاده
