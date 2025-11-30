# حل مشکل Timeout در سیستم مرکزی

**تاریخ:** 2025-11-30  
**وضعیت:** ✅ حل شد

---

## 🔴 مشکل

سیستم کاربران هنگام ارسال درخواست با فایل‌های ضمیمه، خطای **Timeout** دریافت می‌کرد.

### درخواست ارسالی (صحیح بود):
```json
POST https://core.tejarat.chat/api/v1/query/
{
  "query": "این اسناد را بررسی کن",
  "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
  "file_attachments": [
    {
      "filename": "contract.pdf",
      "minio_url": "temp_uploads/.../contract.pdf",
      "file_type": "application/pdf"
    }
  ]
}
```

**خطا:** 504 Gateway Timeout

---

## 🔍 علت اصلی

سرور Core API در حال **crash** بود به دلیل:

```python
ModuleNotFoundError: No module named 'boto3'
```

### چرا این اتفاق افتاد؟

1. کد جدید `storage_service.py` نیاز به `boto3` دارد
2. `boto3` در `requirements.txt` بود اما در container نصب نشده بود
3. هر بار که درخواست می‌آمد، سرور crash می‌کرد
4. Nginx بعد از 60 ثانیه timeout می‌داد

---

## ✅ راه‌حل

### مرحله 1: نصب boto3
```bash
docker exec core-api pip install boto3
```

### مرحله 2: Restart سرور
```bash
docker restart core-api
```

### مرحله 3: بررسی
```bash
curl http://localhost:7001/health
# {"status":"healthy",...}
```

---

## 🧪 تست

### تست ساده (بدون فایل):
```bash
curl -X POST 'https://core.tejarat.chat/api/v1/query/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{"query": "سلام", "language": "fa"}'
```

**انتظار:** پاسخ سریع (1-2 ثانیه)

### تست با فایل:
```bash
curl -X POST 'https://core.tejarat.chat/api/v1/query/' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{
    "query": "این سند را بررسی کن",
    "file_attachments": [{
      "filename": "test.pdf",
      "minio_url": "temp_uploads/user/file.pdf",
      "file_type": "application/pdf"
    }]
  }'
```

**انتظار:** پاسخ در 5-10 ثانیه (بسته به حجم فایل)

---

## ⚠️ نکات مهم

### 1. زمان پردازش

| نوع درخواست | زمان معمول |
|-------------|-----------|
| سوال ساده | 1-3 ثانیه |
| سوال با context | 2-4 ثانیه |
| سوال + 1 فایل PDF | 4-8 ثانیه |
| سوال + 1 تصویر (OCR) | 6-12 ثانیه |
| سوال + 5 فایل | 15-30 ثانیه |

### 2. Timeout تنظیمات

**Nginx (در سیستم کاربران):**
```nginx
proxy_read_timeout 300s;  # 5 دقیقه
proxy_connect_timeout 60s;
```

**FastAPI (در Core):**
```python
# Timeout خودکار ندارد
# اما classification timeout: 5 ثانیه
```

### 3. MinIO Connection

سرور Core باید به MinIO دسترسی داشته باشد:

```bash
# تست دسترسی
docker exec core-api curl -I https://s3.tejarat.chat
# انتظار: 200 OK یا 403 Forbidden (نه timeout)
```

---

## 🚨 مشکلات احتمالی آینده

### مشکل 1: Timeout واقعی (فایل بزرگ)

**علامت:**
- درخواست بیش از 5 دقیقه طول می‌کشد
- فایل‌های بسیار بزرگ (>10MB)

**راه‌حل:**
```python
# در storage_service.py
# افزایش timeout برای download
self.s3_client.meta.client.meta.events.register(
    'request-created',
    lambda **kwargs: kwargs['request'].timeout = 300
)
```

### مشکل 2: MinIO Unreachable

**علامت:**
```
Failed to download file from MinIO: Connection timeout
```

**راه‌حل:**
```bash
# بررسی network
docker exec core-api ping s3.tejarat.chat

# بررسی DNS
docker exec core-api nslookup s3.tejarat.chat

# بررسی credentials
docker exec core-api env | grep S3_
```

### مشکل 3: LLM Timeout

**علامت:**
```
Classification timeout (5s), defaulting to business question
```

**راه‌حل:**
```bash
# غیرفعال کردن classification
echo "ENABLE_QUERY_CLASSIFICATION=false" >> /srv/.env
docker restart core-api
```

---

## 📊 مانیتورینگ

### بررسی لاگ‌ها:
```bash
# خطاها
docker logs core-api --tail 100 | grep -i error

# Timeout ها
docker logs core-api --tail 100 | grep -i timeout

# MinIO
docker logs core-api --tail 100 | grep -i minio

# File processing
docker logs core-api --tail 100 | grep -i "file"
```

### متریک‌های مهم:
- **Response time:** باید کمتر از 30 ثانیه باشد
- **Error rate:** باید کمتر از 1% باشد
- **Memory usage:** نباید بیش از 2GB باشد

---

## ✅ چک‌لیست برای تیم Users

قبل از گزارش مشکل Timeout، این موارد را بررسی کنید:

- [ ] سرور Core در حال اجرا است؟ `curl https://core.tejarat.chat/health`
- [ ] JWT token معتبر است؟
- [ ] فایل‌ها در MinIO موجود هستند؟
- [ ] `minio_url` صحیح است؟ (فقط object key، نه URL کامل)
- [ ] حجم فایل‌ها معقول است؟ (<5MB)
- [ ] تعداد فایل‌ها کمتر از 5 است؟

---

## 📞 در صورت مشکل

1. **بررسی لاگ Core:**
   ```bash
   docker logs core-api --tail 50
   ```

2. **بررسی health:**
   ```bash
   curl https://core.tejarat.chat/health
   ```

3. **تست ساده:**
   ```bash
   curl -X POST https://core.tejarat.chat/api/v1/query/ \
     -H "Authorization: Bearer TOKEN" \
     -d '{"query": "تست"}'
   ```

4. **اگر مشکل ادامه داشت:**
   - لاگ کامل را ارسال کنید
   - درخواست دقیق (با curl) را ارسال کنید
   - زمان وقوع مشکل را مشخص کنید

---

**مشکل حل شد!** ✅

سیستم کاربران می‌تواند درخواست‌های خود را ارسال کند.
