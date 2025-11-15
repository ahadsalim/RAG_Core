# وضعیت Celery در پروژه

## خلاصه

✅ **Celery به طور کامل پیاده‌سازی شده است** و آماده استفاده در production.

## تغییرات انجام شده

### قبل (2025-11-14 قبل از ساعت 20:00)
- ❌ Celery پیاده‌سازی نشده بود
- ❌ Workers با خطا exit می‌کردند
- ❌ هیچ task تعریف نشده بود

### بعد (2025-11-15 ساعت 04:25)
- ✅ Celery کامل پیاده‌سازی شد
- ✅ 15+ task برای عملیات مختلف
- ✅ Integration با endpoints موجود
- ✅ Beat schedule برای taskهای دوره‌ای
- ✅ Monitoring via Flower
- ✅ Task management API

## فایل‌های ایجاد شده

```
app/
├── celery_app.py                    # پیکربندی Celery
├── tasks/
│   ├── __init__.py
│   ├── sync.py                      # 4 tasks
│   ├── notifications.py             # 3 tasks
│   ├── cleanup.py                   # 4 tasks
│   └── user.py                      # 4 tasks
└── api/v1/endpoints/
    └── tasks.py                     # API برای مدیریت tasks
```

## Tasks پیاده‌سازی شده

### Sync Tasks (4 tasks)
1. `sync_embeddings_task` - همگام‌سازی embeddings
2. `process_sync_queue` - پردازش صف (هر 5 دقیقه)
3. `trigger_full_sync_task` - همگام‌سازی کامل
4. `delete_document_embeddings_task` - حذف embeddings

### Notification Tasks (3 tasks)
1. `send_query_result_to_users` - ارسال نتیجه به سیستم کاربران ⭐
2. `send_usage_statistics` - ارسال آمار (هر ساعت)
3. `send_system_notification` - اعلان‌های سیستمی

### Cleanup Tasks (4 tasks)
1. `cleanup_old_cache` - پاکسازی cache (هر 6 ساعت)
2. `cleanup_query_cache` - پاکسازی query cache (روزانه)
3. `cleanup_old_conversations` - آرشیو مکالمات قدیمی
4. `cleanup_failed_tasks` - پاکسازی taskهای failed

### User Tasks (4 tasks)
1. `reset_user_daily_limit` - ریست محدودیت یک کاربر
2. `reset_all_daily_limits` - ریست همه (نیمه‌شب)
3. `update_user_statistics` - به‌روزرسانی آمار ⭐
4. `calculate_user_tier` - محاسبه tier کاربر

⭐ = استفاده خودکار بعد از هر query

## Integration با Endpoints

### `/api/v1/query/` (POST)
```python
# بعد از هر query موفق:
send_query_result_to_users.delay(...)  # ارسال به سیستم کاربران
update_user_statistics.delay(user_id)  # به‌روزرسانی آمار
```

### `/api/v1/sync/trigger-full-sync` (POST)
```python
# استفاده از Celery به جای background task
task = trigger_full_sync_task.delay(batch_size=100)
return {"task_id": task.id}
```

### `/api/v1/sync/document/{id}` (DELETE)
```python
# حذف async via Celery
task = delete_document_embeddings_task.delay(document_id)
return {"task_id": task.id}
```

## API Endpoints جدید

### `/api/v1/tasks/`

- `GET /status/{task_id}` - وضعیت task
- `GET /list` - لیست taskهای فعال
- `POST /revoke/{task_id}` - لغو task
- `GET /workers` - آمار workers
- `POST /trigger/cleanup-cache` - اجرای دستی cleanup
- `POST /trigger/reset-daily-limits` - اجرای دستی reset
- `POST /trigger/send-statistics` - اجرای دستی ارسال آمار

## Beat Schedule (Periodic Tasks)

| Task | Schedule | Description |
|------|----------|-------------|
| `reset_all_daily_limits` | روزانه 00:00 | ریست محدودیت کاربران |
| `cleanup_old_cache` | هر 6 ساعت | پاکسازی cache |
| `cleanup_query_cache` | روزانه 02:00 | پاکسازی query cache |
| `process_sync_queue` | هر 5 دقیقه | پردازش صف sync |
| `send_usage_statistics` | هر ساعت | ارسال آمار به Users |

## Docker Configuration

```yaml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info --concurrency=4 --queues=sync,notifications,cleanup,user
  restart: unless-stopped

celery-beat:
  command: celery -A app.celery_app beat --loglevel=info
  restart: unless-stopped

flower:
  ports: ["5555:5555"]
  # Access: http://localhost:5555
```

## راه‌اندازی

```bash
# Start services
cd /srv/deployment/docker
docker-compose up -d celery-worker celery-beat flower

# Check logs
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat

# Access Flower
http://localhost:5555
```

## تست

```bash
# Test via API
curl -X POST "http://localhost:7001/api/v1/tasks/trigger/cleanup-cache" \
  -H "X-API-Key: your-api-key"

# Check task status
curl "http://localhost:7001/api/v1/tasks/status/{task_id}" \
  -H "X-API-Key: your-api-key"

# List workers
curl "http://localhost:7001/api/v1/tasks/workers" \
  -H "X-API-Key: your-api-key"
```

## مستندات

مستندات کامل در:
- `/srv/document/CELERY_IMPLEMENTATION.md` - راهنمای کامل پیاده‌سازی
- `/srv/deployment/README.md` - راهنمای deployment

## نتیجه‌گیری

✅ Celery به طور کامل پیاده‌سازی و آماده استفاده است
✅ ارسال خودکار نتایج query به سیستم کاربران
✅ پاکسازی خودکار سیستم
✅ همگام‌سازی بهینه با Ingest
✅ مانیتورینگ کامل via Flower
✅ API برای مدیریت tasks

**سیستم حالا production-ready است! 🎉**
