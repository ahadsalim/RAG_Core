# بررسی دقیق استفاده از Celery در پروژه

## تاریخ بررسی: 2025-11-04

---

## ❓ سوال: آیا Celery در پروژه استفاده می‌شود؟

### ✅ پاسخ: خیر، Celery استفاده نمی‌شود

---

## 🔍 جزئیات بررسی

### 1. بررسی Import های Celery
```bash
grep -r "from celery import" app/
grep -r "import celery" app/
```
**نتیجه:** هیچ import از Celery پیدا نشد ❌

### 2. بررسی Celery Decorators
```bash
grep -r "@task\|@shared_task" app/
```
**نتیجه:** هیچ decorator از Celery پیدا نشد ❌

### 3. بررسی Celery Task Calls
```bash
grep -r "\.delay(\|\.apply_async(" app/
```
**نتیجه:** هیچ task call پیدا نشد ❌

### 4. بررسی فایل celery.py
```bash
find app/ -name "celery.py"
```
**نتیجه:** فایل celery.py وجود ندارد ❌

### 5. بررسی استفاده از Celery Settings
```bash
grep -r "settings.celery" app/
```
**نتیجه:** هیچ استفاده‌ای از celery settings پیدا نشد ❌

---

## ✅ چه چیزی استفاده می‌شود؟

### FastAPI BackgroundTasks

پروژه از **FastAPI BackgroundTasks** استفاده می‌کند که:
- ✅ Built-in FastAPI است
- ✅ برای taskهای سبک و کوتاه مناسب است
- ✅ نیازی به Celery worker ندارد
- ✅ در همان process اجرا می‌شود

**مثال‌های استفاده:**

#### 1. در `query.py`:
```python
from fastapi import BackgroundTasks

@router.post("/")
async def process_query(
    background_tasks: BackgroundTasks,
    ...
):
    # Task: Reset user daily limit
    background_tasks.add_task(reset_user_daily_limit_if_needed, user.id)
```

#### 2. در `sync.py`:
```python
@router.post("/trigger-full-sync")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    ...
):
    # Task: Run full sync
    background_tasks.add_task(run_full_sync)
```

---

## 📊 تفاوت FastAPI BackgroundTasks و Celery

| ویژگی | FastAPI BackgroundTasks | Celery |
|-------|------------------------|--------|
| نصب | Built-in | نیاز به نصب جداگانه |
| Worker | نیاز ندارد | نیاز به worker جداگانه |
| مناسب برای | Taskهای سبک (< 30 ثانیه) | Taskهای سنگین و طولانی |
| Retry | خیر | بله |
| Scheduling | خیر | بله (با Beat) |
| Monitoring | محدود | کامل (با Flower) |
| استفاده در پروژه | ✅ بله | ❌ خیر |

---

## 🔧 تغییرات اعمال شده

### 1. غیرفعال کردن Celery Workers در docker-compose.yml
```yaml
# celery-worker: Commented out
# celery-beat: Commented out
# flower: Commented out
```

**دلیل:** چون استفاده نمی‌شوند و فقط منابع مصرف می‌کنند

### 2. Optional کردن Celery Settings در settings.py
```python
# قبل:
celery_broker_url: RedisDsn  # اجباری بود
celery_result_backend: RedisDsn  # اجباری بود

# بعد:
celery_broker_url: Optional[RedisDsn] = None  # اختیاری شد
celery_result_backend: Optional[RedisDsn] = None  # اختیاری شد
```

**دلیل:** چون در کد استفاده نمی‌شوند

---

## ⚠️ آیا مشکلی ایجاد می‌شود؟

### ✅ خیر، هیچ مشکلی ایجاد نمی‌شود چون:

1. **Celery در کد استفاده نشده است**
   - هیچ task تعریف نشده
   - هیچ worker call نشده
   - فایل celery.py وجود ندارد

2. **FastAPI BackgroundTasks جایگزین است**
   - همه background tasks از FastAPI هستند
   - نیازی به Celery ندارند
   - در همان process اجرا می‌شوند

3. **تست شده و کار می‌کند**
   - API بعد از تغییرات restart شد
   - Health check موفق است
   - سایت کاملاً کار می‌کند

---

## 🔮 اگر در آینده نیاز به Celery شد

### مراحل فعال‌سازی:

1. **ایجاد فایل `app/celery.py`:**
```python
from celery import Celery
from app.config.settings import settings

celery_app = Celery(
    "core",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend)
)
```

2. **Uncomment کردن سرویس‌ها در docker-compose.yml:**
```bash
# Remove # from celery-worker, celery-beat, flower
```

3. **تعریف taskها:**
```python
from app.celery import celery_app

@celery_app.task
def my_heavy_task():
    # Your code here
    pass
```

4. **Restart کردن:**
```bash
docker-compose -f deployment/docker/docker-compose.yml up -d
```

---

## 📝 نتیجه‌گیری

✅ **Celery در پروژه استفاده نمی‌شود**
✅ **FastAPI BackgroundTasks کافی است**
✅ **غیرفعال کردن Celery workers مشکلی ایجاد نمی‌کند**
✅ **منابع سرور بهینه‌تر مصرف می‌شود**
✅ **کد تمیزتر و ساده‌تر است**

---

## 🧪 تست نهایی

```bash
# Test API
curl -s https://core.arpanet.ir/api/v1/health
# Result: {"status":"healthy","service":"core","version":"1.0.0"}

# Check running containers
docker ps
# Result: core-api, nginx, postgres, redis, qdrant (NO celery workers)

# Test background tasks (query endpoint)
curl -X POST https://core.arpanet.ir/api/v1/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Result: Works fine with FastAPI BackgroundTasks
```

**همه چیز کار می‌کند! ✅**
