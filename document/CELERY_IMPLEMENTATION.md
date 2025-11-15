# پیاده‌سازی Celery در سیستم RAG Core

## خلاصه

Celery به طور کامل در پروژه پیاده‌سازی شده و برای عملیات asynchronous زیر استفاده می‌شود:

1. **Synchronization** - همگام‌سازی با سیستم Ingest
2. **Notifications** - ارسال اعلان‌ها به سیستم کاربران
3. **Cleanup** - پاکسازی و نگهداری سیستم
4. **User Management** - مدیریت کاربران و آمار

---

## ساختار فایل‌ها

```
app/
├── celery_app.py              # پیکربندی اصلی Celery
└── tasks/
    ├── __init__.py           # Export همه tasks
    ├── sync.py               # Tasks همگام‌سازی
    ├── notifications.py      # Tasks اعلان‌ها
    ├── cleanup.py            # Tasks پاکسازی
    └── user.py               # Tasks کاربران
```

---

## Tasks پیاده‌سازی شده

### 1. Sync Tasks (`app/tasks/sync.py`)

#### `sync_embeddings_task`
- همگام‌سازی embeddings از Ingest به Qdrant
- پارامترها: `batch_size`, `since`
- Retry: 3 بار با exponential backoff
- Queue: `sync`

#### `process_sync_queue`
- پردازش صف همگام‌سازی
- اجرای دوره‌ای: هر 5 دقیقه (via Beat)
- Queue: `sync`

#### `trigger_full_sync_task`
- همگام‌سازی کامل (عملیات سنگین)
- Time limit: 1 ساعت
- Retry: 1 بار
- Queue: `sync`

#### `delete_document_embeddings_task`
- حذف embeddings یک سند
- Retry: 3 بار
- Queue: `sync`

---

### 2. Notification Tasks (`app/tasks/notifications.py`)

#### `send_query_result_to_users`
- ارسال نتیجه query به سیستم کاربران
- پارامترها: `user_id`, `conversation_id`, `message_id`, `query`, `answer`, `sources`, `tokens_used`, `processing_time_ms`
- Retry: 3 بار
- Queue: `notifications`
- **استفاده**: بعد از هر query موفق

#### `send_usage_statistics`
- ارسال آمار استفاده به سیستم کاربران
- اجرای دوره‌ای: هر ساعت (via Beat)
- Queue: `notifications`

#### `send_system_notification`
- ارسال اعلان سیستمی به کاربران
- پارامترها: `notification_type`, `title`, `message`, `user_ids`, `metadata`
- Retry: 3 بار
- Queue: `notifications`

---

### 3. Cleanup Tasks (`app/tasks/cleanup.py`)

#### `cleanup_old_cache`
- پاکسازی cache قدیمی Redis
- اجرای دوره‌ای: هر 6 ساعت (via Beat)
- Queue: `cleanup`

#### `cleanup_query_cache`
- پاکسازی query cache قدیمی از database
- پارامتر: `days` (پیش‌فرض: 30 روز)
- اجرای دوره‌ای: هر روز ساعت 2 صبح (via Beat)
- Queue: `cleanup`

#### `cleanup_old_conversations`
- آرشیو مکالمات قدیمی
- پارامتر: `days` (پیش‌فرض: 90 روز)
- Queue: `cleanup`

#### `cleanup_failed_tasks`
- پاکسازی نتایج taskهای failed از Redis
- Queue: `cleanup`

---

### 4. User Tasks (`app/tasks/user.py`)

#### `reset_user_daily_limit`
- ریست محدودیت روزانه یک کاربر
- پارامتر: `user_id`
- Queue: `user`

#### `reset_all_daily_limits`
- ریست محدودیت روزانه همه کاربران
- اجرای دوره‌ای: هر روز نیمه‌شب (via Beat)
- Queue: `user`

#### `update_user_statistics`
- به‌روزرسانی آمار کاربر
- پارامتر: `user_id`
- Queue: `user`
- **استفاده**: بعد از هر query

#### `calculate_user_tier`
- محاسبه و به‌روزرسانی tier کاربر
- پارامتر: `user_id`
- Queue: `user`

---

## Celery Beat Schedule

وظایف دوره‌ای که به صورت خودکار اجرا می‌شوند:

| Task | Schedule | Description |
|------|----------|-------------|
| `reset_all_daily_limits` | هر روز 00:00 | ریست محدودیت روزانه کاربران |
| `cleanup_old_cache` | هر 6 ساعت | پاکسازی cache قدیمی |
| `cleanup_query_cache` | هر روز 02:00 | پاکسازی query cache |
| `process_sync_queue` | هر 5 دقیقه | پردازش صف همگام‌سازی |
| `send_usage_statistics` | هر ساعت | ارسال آمار به سیستم کاربران |

---

## API Endpoints

### Task Management (`/api/v1/tasks/`)

#### `GET /tasks/status/{task_id}`
دریافت وضعیت یک task

**Response:**
```json
{
  "task_id": "abc123",
  "status": "SUCCESS",
  "result": {...},
  "error": null,
  "traceback": null
}
```

#### `GET /tasks/list`
لیست taskهای فعال، scheduled و reserved

**Response:**
```json
{
  "active": [...],
  "scheduled": [...],
  "reserved": [...]
}
```

#### `POST /tasks/revoke/{task_id}`
لغو یک task در حال اجرا

**Parameters:**
- `terminate`: اگر True، task را فوراً terminate کند

#### `GET /tasks/workers`
آمار workerها

**Response:**
```json
{
  "status": "success",
  "workers": [
    {
      "name": "celery@worker1",
      "stats": {...},
      "queues": [...],
      "registered_tasks": [...]
    }
  ],
  "total_workers": 1
}
```

#### `POST /tasks/trigger/cleanup-cache`
اجرای دستی task پاکسازی cache

#### `POST /tasks/trigger/reset-daily-limits`
اجرای دستی task ریست محدودیت روزانه

#### `POST /tasks/trigger/send-statistics`
اجرای دستی task ارسال آمار

---

## تغییرات در Endpoints موجود

### `/api/v1/query/` (POST)
✅ **اضافه شده**:
- ارسال نتیجه query به سیستم کاربران (via `send_query_result_to_users`)
- به‌روزرسانی آمار کاربر (via `update_user_statistics`)

### `/api/v1/sync/trigger-full-sync` (POST)
✅ **تغییر یافته**:
- استفاده از `trigger_full_sync_task` به جای background task
- برگرداندن `task_id` برای tracking

### `/api/v1/sync/document/{document_id}` (DELETE)
✅ **تغییر یافته**:
- استفاده از `delete_document_embeddings_task` به جای sync delete
- برگرداندن `task_id` برای tracking

---

## پیکربندی Docker

### Celery Worker
```yaml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info --concurrency=4 --queues=sync,notifications,cleanup,user
  restart: unless-stopped
```

**Features:**
- Concurrency: 4 workers
- Queues: sync, notifications, cleanup, user
- Auto-restart on failure

### Celery Beat
```yaml
celery-beat:
  command: celery -A app.celery_app beat --loglevel=info
  restart: unless-stopped
```

**Features:**
- Scheduler برای taskهای دوره‌ای
- Auto-restart on failure

### Flower (Monitoring)
```yaml
flower:
  image: mher/flower:2.0.1
  ports:
    - "5555:5555"
```

**Access:** `http://localhost:5555`

---

## نحوه استفاده

### 1. اجرای Task از کد

```python
from app.tasks.sync import sync_embeddings_task

# Async execution
task = sync_embeddings_task.delay(batch_size=100)
print(f"Task ID: {task.id}")

# Check status
from celery.result import AsyncResult
result = AsyncResult(task.id)
print(f"Status: {result.status}")
```

### 2. اجرای Task از API

```bash
# Trigger full sync
curl -X POST "http://localhost:7001/api/v1/sync/trigger-full-sync" \
  -H "X-API-Key: your-api-key"

# Check task status
curl "http://localhost:7001/api/v1/tasks/status/{task_id}" \
  -H "X-API-Key: your-api-key"
```

### 3. مانیتورینگ با Flower

```bash
# Open in browser
http://localhost:5555

# View:
# - Active tasks
# - Task history
# - Worker status
# - Task statistics
```

---

## Monitoring و Debugging

### لاگ‌های Celery Worker
```bash
docker-compose -f deployment/docker/docker-compose.yml logs -f celery-worker
```

### لاگ‌های Celery Beat
```bash
docker-compose -f deployment/docker/docker-compose.yml logs -f celery-beat
```

### بررسی وضعیت Workers
```bash
# Via API
curl "http://localhost:7001/api/v1/tasks/workers" \
  -H "X-API-Key: your-api-key"

# Via Flower
http://localhost:5555/workers
```

### بررسی Taskهای فعال
```bash
# Via API
curl "http://localhost:7001/api/v1/tasks/list" \
  -H "X-API-Key: your-api-key"

# Via Flower
http://localhost:5555/tasks
```

---

## مثال‌های کاربردی

### 1. ارسال نتیجه Query به سیستم کاربران

```python
# Automatically called after each query
from app.tasks.notifications import send_query_result_to_users

send_query_result_to_users.delay(
    user_id="user-123",
    conversation_id="conv-456",
    message_id="msg-789",
    query="سوال کاربر",
    answer="پاسخ سیستم",
    sources=["source1", "source2"],
    tokens_used=150,
    processing_time_ms=1200
)
```

### 2. همگام‌سازی اسناد جدید

```python
from app.tasks.sync import sync_embeddings_task
from datetime import datetime, timedelta

# Sync last 24 hours
since = (datetime.utcnow() - timedelta(days=1)).isoformat()
task = sync_embeddings_task.delay(batch_size=100, since=since)
```

### 3. پاکسازی دستی Cache

```bash
curl -X POST "http://localhost:7001/api/v1/tasks/trigger/cleanup-cache" \
  -H "X-API-Key: your-api-key"
```

---

## مزایای پیاده‌سازی

✅ **Reliability**: Retry mechanism برای taskهای failed
✅ **Scalability**: امکان افزودن workerهای بیشتر
✅ **Monitoring**: Flower برای مانیتورینگ real-time
✅ **Scheduling**: Beat برای taskهای دوره‌ای
✅ **Separation**: جداسازی عملیات سنگین از API
✅ **Integration**: ارسال خودکار نتایج به سیستم کاربران
✅ **Maintenance**: پاکسازی خودکار سیستم

---

## نکات مهم

1. **API Keys**: برای استفاده از endpoints مدیریتی، API key لازم است
2. **Queues**: Taskها در queueهای مختلف برای priority management
3. **Retry**: همه taskها retry mechanism دارند
4. **Logging**: همه taskها لاگ می‌کنند
5. **Error Handling**: خطاها به درستی handle می‌شوند

---

## راه‌اندازی

```bash
# Start all services
cd /srv/deployment/docker
docker-compose up -d

# Check Celery workers
docker-compose logs -f celery-worker

# Check Celery beat
docker-compose logs -f celery-beat

# Access Flower
http://localhost:5555
```

---

## مستندات بیشتر

- [Celery Documentation](https://docs.celeryq.dev/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
