# خلاصه پیاده‌سازی Celery در پروژه RAG Core

## ✅ کارهای انجام شده

### 1. ایجاد ماژول Celery
- **فایل**: `/srv/app/celery_app.py`
- **محتوا**: پیکربندی کامل Celery با Beat schedule
- **Features**:
  - Task routing به 4 queue مختلف
  - Retry mechanism
  - Time limits
  - Beat schedule برای 5 task دوره‌ای

### 2. ایجاد 15 Task مختلف

#### Sync Tasks (4 tasks)
- `sync_embeddings_task` - همگام‌سازی embeddings از Ingest
- `process_sync_queue` - پردازش صف همگام‌سازی (هر 5 دقیقه)
- `trigger_full_sync_task` - همگام‌سازی کامل
- `delete_document_embeddings_task` - حذف embeddings سند

#### Notification Tasks (3 tasks)
- `send_query_result_to_users` - **ارسال نتیجه query به سیستم کاربران** ⭐
- `send_usage_statistics` - ارسال آمار ساعتی به Users
- `send_system_notification` - ارسال اعلان‌های سیستمی

#### Cleanup Tasks (4 tasks)
- `cleanup_old_cache` - پاکسازی cache Redis (هر 6 ساعت)
- `cleanup_query_cache` - پاکسازی query cache (روزانه)
- `cleanup_old_conversations` - آرشیو مکالمات قدیمی
- `cleanup_failed_tasks` - پاکسازی taskهای failed

#### User Tasks (4 tasks)
- `reset_user_daily_limit` - ریست محدودیت یک کاربر
- `reset_all_daily_limits` - ریست همه کاربران (نیمه‌شب)
- `update_user_statistics` - **به‌روزرسانی آمار کاربر** ⭐
- `calculate_user_tier` - محاسبه tier کاربر

⭐ = استفاده خودکار بعد از هر query

### 3. Integration با Endpoints موجود

#### `/api/v1/query/` (POST)
```python
# اضافه شده:
send_query_result_to_users.delay(...)  # ارسال به سیستم کاربران
update_user_statistics.delay(user_id)  # به‌روزرسانی آمار
```

#### `/api/v1/sync/trigger-full-sync` (POST)
```python
# تغییر یافته:
task = trigger_full_sync_task.delay(batch_size=100)
return {"task_id": task.id}  # برگرداندن task_id برای tracking
```

#### `/api/v1/sync/document/{id}` (DELETE)
```python
# تغییر یافته:
task = delete_document_embeddings_task.delay(document_id)
return {"task_id": task.id}
```

### 4. API جدید برای مدیریت Tasks

**Endpoint**: `/api/v1/tasks/`

- `GET /status/{task_id}` - دریافت وضعیت task
- `GET /list` - لیست taskهای فعال
- `POST /revoke/{task_id}` - لغو task
- `GET /workers` - آمار workers
- `POST /trigger/cleanup-cache` - اجرای دستی cleanup
- `POST /trigger/reset-daily-limits` - اجرای دستی reset
- `POST /trigger/send-statistics` - اجرای دستی ارسال آمار

### 5. به‌روزرسانی Docker Compose

```yaml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info --concurrency=4 --queues=sync,notifications,cleanup,user
  restart: unless-stopped
  environment:
    - USERS_API_URL=${USERS_API_URL}
    - USERS_API_KEY=${USERS_API_KEY}
    # + سایر متغیرها

celery-beat:
  command: celery -A app.celery_app beat --loglevel=info
  restart: unless-stopped

flower:
  ports: ["5555:5555"]
```

### 6. مستندات کامل

- `/srv/document/CELERY_IMPLEMENTATION.md` - راهنمای کامل پیاده‌سازی
- `/srv/deployment/CELERY_STATUS.md` - وضعیت و تغییرات
- `/srv/CELERY_SUMMARY.md` - این فایل

---

## 🎯 موارد استفاده اصلی

### 1. ارسال نتیجه Query به سیستم کاربران
**هدف**: اطلاع‌رسانی real-time به سیستم Users

```python
# بعد از هر query موفق
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

**Payload ارسالی**:
```json
{
  "event_type": "query_completed",
  "user_id": "user-123",
  "timestamp": "2025-11-15T04:25:00Z",
  "data": {
    "conversation_id": "conv-456",
    "message_id": "msg-789",
    "query": "سوال کاربر",
    "answer": "پاسخ سیستم",
    "sources": ["source1", "source2"],
    "tokens_used": 150,
    "processing_time_ms": 1200
  }
}
```

### 2. ارسال آمار ساعتی
**هدف**: گزارش‌گیری و مانیتورینگ

```python
# هر ساعت (via Beat)
send_usage_statistics.delay()
```

**Payload ارسالی**:
```json
{
  "event_type": "usage_statistics",
  "timestamp": "2025-11-15T04:00:00Z",
  "data": {
    "total_queries": 150,
    "total_tokens": 45000,
    "active_users": 25,
    "period_start": "2025-11-15T03:00:00Z",
    "period_end": "2025-11-15T04:00:00Z"
  }
}
```

### 3. همگام‌سازی با Ingest
**هدف**: sync خودکار embeddings

```python
# هر 5 دقیقه (via Beat)
process_sync_queue.delay()

# یا manual trigger
trigger_full_sync_task.delay(batch_size=100)
```

### 4. پاکسازی خودکار
**هدف**: نگهداری سیستم

```python
# هر 6 ساعت
cleanup_old_cache.delay()

# هر روز ساعت 2 صبح
cleanup_query_cache.delay(days=30)
```

### 5. مدیریت کاربران
**هدف**: ریست محدودیت‌ها و آمار

```python
# هر روز نیمه‌شب
reset_all_daily_limits.delay()

# بعد از هر query
update_user_statistics.delay(user_id)
```

---

## 📊 Beat Schedule (Taskهای دوره‌ای)

| Task | Schedule | Queue | Description |
|------|----------|-------|-------------|
| `reset_all_daily_limits` | روزانه 00:00 | user | ریست محدودیت روزانه |
| `cleanup_old_cache` | هر 6 ساعت | cleanup | پاکسازی cache |
| `cleanup_query_cache` | روزانه 02:00 | cleanup | پاکسازی query cache |
| `process_sync_queue` | هر 5 دقیقه | sync | پردازش صف sync |
| `send_usage_statistics` | هر ساعت | notifications | ارسال آمار |

---

## 🚀 راه‌اندازی

```bash
# 1. Start services
cd /srv/deployment/docker
docker-compose up -d celery-worker celery-beat flower

# 2. Check logs
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat

# 3. Access Flower (monitoring)
http://localhost:5555

# 4. Test via API
curl -X POST "http://localhost:7001/api/v1/tasks/trigger/cleanup-cache" \
  -H "X-API-Key: your-api-key"

# 5. Check task status
curl "http://localhost:7001/api/v1/tasks/status/{task_id}" \
  -H "X-API-Key: your-api-key"
```

---

## 📁 ساختار فایل‌ها

```
/srv/
├── app/
│   ├── celery_app.py                 # پیکربندی Celery
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── sync.py                   # 4 tasks
│   │   ├── notifications.py          # 3 tasks
│   │   ├── cleanup.py                # 4 tasks
│   │   └── user.py                   # 4 tasks
│   └── api/v1/endpoints/
│       ├── query.py                  # ✏️ Modified
│       ├── sync.py                   # ✏️ Modified
│       └── tasks.py                  # ✨ New
├── deployment/
│   ├── docker/
│   │   └── docker-compose.yml        # ✏️ Modified
│   ├── CELERY_STATUS.md              # ✏️ Updated
│   └── README.md
└── document/
    └── CELERY_IMPLEMENTATION.md      # ✨ New
```

---

## ✅ چک‌لیست

- [x] ایجاد `celery_app.py` با پیکربندی کامل
- [x] ایجاد 15 task در 4 دسته
- [x] Integration با `/api/v1/query/` برای ارسال به Users
- [x] Integration با `/api/v1/sync/` برای sync operations
- [x] ایجاد `/api/v1/tasks/` برای مدیریت
- [x] به‌روزرسانی `docker-compose.yml`
- [x] Beat schedule برای 5 task دوره‌ای
- [x] Retry mechanism برای همه tasks
- [x] Logging برای همه tasks
- [x] Error handling
- [x] Queue routing (4 queues)
- [x] Monitoring via Flower
- [x] مستندات کامل

---

## 🎉 نتیجه

✅ **Celery به طور کامل پیاده‌سازی شد**

**قابلیت‌های اضافه شده:**
1. ✅ ارسال خودکار نتایج query به سیستم کاربران
2. ✅ ارسال آمار ساعتی به سیستم کاربران
3. ✅ همگام‌سازی خودکار با Ingest (هر 5 دقیقه)
4. ✅ پاکسازی خودکار cache و database
5. ✅ ریست خودکار محدودیت‌های روزانه
6. ✅ به‌روزرسانی خودکار آمار کاربران
7. ✅ مانیتورینگ کامل via Flower
8. ✅ API برای مدیریت tasks
9. ✅ Retry mechanism برای reliability
10. ✅ Queue routing برای priority management

**سیستم حالا production-ready است! 🚀**
