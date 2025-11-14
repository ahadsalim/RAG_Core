# وضعیت Celery در پروژه

## خلاصه

**Celery در حال حاضر پیاده‌سازی نشده است** و سرویس‌های `celery-worker` و `celery-beat` در `docker-compose.yml` غیرفعال شده‌اند.

## چرا Celery غیرفعال شد؟

### مشکل اصلی
زمانی که سیستم را راه‌اندازی کردیم، سرویس‌های Celery با خطای زیر مواجه شدند:

```
Error: Unable to load celery application.
The module app.celery was not found.
```

### علت
1. **ماژول Celery وجود ندارد**: فایل `app/celery.py` یا `app/celery/__init__.py` در پروژه وجود ندارد
2. **تنظیمات Celery ناقص است**: در `app/config/settings.py` فقط متغیرهای محیطی Celery تعریف شده، اما خود Celery instance ایجاد نشده
3. **Task‌ها تعریف نشده‌اند**: هیچ Celery task در پروژه پیاده‌سازی نشده

### تصمیم
برای جلوگیری از خطاهای مکرر و اجرای صحیح سایر سرویس‌ها، Celery workers را موقتاً غیرفعال کردیم:

```bash
docker-compose stop celery-worker celery-beat
```

## چه زمانی Celery نیاز است؟

Celery برای اجرای وظایف زمان‌بر و asynchronous استفاده می‌شود. در سیستم RAG Core، موارد زیر می‌توانند از Celery استفاده کنند:

### کاربردهای پیشنهادی:
1. **پردازش اسناد**: 
   - استخراج متن از PDF/Word
   - OCR برای تصاویر
   - تبدیل فایل‌های صوتی به متن (Whisper)

2. **Embedding و Indexing**:
   - تولید embedding برای اسناد جدید
   - به‌روزرسانی vector database
   - Re-indexing اسناد

3. **وظایف دوره‌ای**:
   - پاکسازی cache قدیمی
   - آرشیو لاگ‌ها
   - گزارش‌گیری روزانه/هفتگی

4. **ارسال اعلان‌ها**:
   - ایمیل
   - Webhook notifications
   - پیامک

## چگونه Celery را فعال کنیم؟

### مرحله 1: ایجاد ماژول Celery

ایجاد فایل `/srv/app/celery_app.py`:

```python
"""
Celery Application Configuration
"""
from celery import Celery
from app.config.settings import settings

# Create Celery instance
celery_app = Celery(
    "core_tasks",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.tasks'])
```

### مرحله 2: ایجاد Tasks

ایجاد دایرکتوری و فایل `/srv/app/tasks/__init__.py`:

```python
"""
Celery Tasks
"""
from app.celery_app import celery_app

@celery_app.task(name="tasks.example_task")
def example_task(param: str) -> str:
    """Example Celery task"""
    return f"Processed: {param}"

@celery_app.task(name="tasks.process_document")
def process_document(document_id: int) -> dict:
    """Process document asynchronously"""
    # Implementation here
    return {"status": "success", "document_id": document_id}
```

### مرحله 3: به‌روزرسانی docker-compose command

در `/srv/deployment/docker/docker-compose.yml`:

```yaml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info

celery-beat:
  command: celery -A app.celery_app beat --loglevel=info
```

### مرحله 4: راه‌اندازی مجدد

```bash
docker-compose -f /srv/deployment/docker/docker-compose.yml up -d celery-worker celery-beat
```

## وضعیت فعلی سرویس‌ها

✅ **فعال و سالم:**
- `core-api`: API اصلی
- `postgres-core`: دیتابیس
- `redis-core`: Cache و message broker
- `qdrant`: Vector database
- `nginx-proxy-manager`: Reverse proxy با SSL
- `flower`: Celery monitoring UI (در انتظار Celery)

🔴 **غیرفعال:**
- `celery-worker`: نیاز به پیاده‌سازی
- `celery-beat`: نیاز به پیاده‌سازی

## نتیجه‌گیری

Celery یک قابلیت اختیاری است که در آینده می‌تواند برای بهبود performance و مدیریت وظایف زمان‌بر اضافه شود. در حال حاضر، سیستم بدون Celery به طور کامل کار می‌کند و تمام APIها قابل استفاده هستند.

اگر نیاز به اجرای وظایف asynchronous دارید، می‌توانید از مراحل بالا برای فعال‌سازی Celery استفاده کنید.

## منابع

- [Celery Documentation](https://docs.celeryq.dev/)
- [FastAPI with Celery](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Flower Monitoring](https://flower.readthedocs.io/)
