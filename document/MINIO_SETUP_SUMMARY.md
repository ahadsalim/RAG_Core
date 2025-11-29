# خلاصه پیکربندی MinIO

**تاریخ:** 2025-11-29  
**وضعیت:** ✅ کد به‌روز شد | ⚠️ سرور در دسترس نیست

---

## ✅ تغییرات اعمال شده

### 1. اضافه شدن تنظیمات باکت به `.env`

```bash
# MinIO Buckets
S3_DOCUMENTS_BUCKET=advisor-docs      # اسناد از Ingest
S3_TEMP_BUCKET=temp-userfile          # فایل‌های موقت Users
```

**مسیر:** `/srv/.env` خطوط 166-170

---

### 2. به‌روزرسانی `settings.py`

```python
# File Storage (S3/MinIO)
s3_documents_bucket: str = Field(default="advisor-docs")
s3_temp_bucket: str = Field(default="temp-userfile")
```

**مسیر:** `/srv/app/config/settings.py` خطوط 176-177

---

### 3. به‌روزرسانی `storage_service.py`

**تغییرات:**
- اضافه شدن `self.documents_bucket` و `self.temp_bucket`
- بررسی وجود هر دو باکت در `__init__`
- استفاده از `temp_bucket` برای آپلود فایل‌های موقت
- اضافه شدن پارامتر `bucket` به `download_temp_file`

**مسیر:** `/srv/app/services/storage_service.py`

```python
# خطوط 40-42
self.documents_bucket = settings.s3_documents_bucket  # advisor-docs
self.temp_bucket = settings.s3_temp_bucket  # temp-userfile

# خط 109
Bucket=self.temp_bucket,  # Use temp-userfile bucket

# خط 144
async def download_temp_file(self, object_key: str, bucket: Optional[str] = None)
```

---

## 📦 باکت‌های MinIO

### 1. `advisor-docs`
- **هدف:** ذخیره اسناد و قوانین از سیستم Ingest
- **محتوا:** فایل‌های PDF، Word، Excel و ...
- **دسترسی:** فقط خواندنی برای RAG Core
- **استفاده:** در RAG Pipeline برای جستجو

### 2. `temp-userfile`
- **هدف:** ذخیره موقت فایل‌های کاربران
- **محتوا:** تصاویر، PDF، TXT ضمیمه شده با Query
- **دسترسی:** خواندن/نوشتن برای RAG Core
- **استفاده:** پردازش OCR و استخراج متن
- **Lifecycle:** حذف خودکار بعد از 24 ساعت

---

## 🔧 نحوه استفاده در کد

### آپلود فایل موقت (از سیستم Users)

```python
from app.services.storage_service import get_storage_service

storage = get_storage_service()

# آپلود به temp-userfile
result = await storage.upload_temp_file(
    file_content=file_bytes,
    filename="document.pdf",
    user_id="user123",
    content_type="application/pdf"
)

# object_key برگشت داده می‌شود
object_key = result['object_key']
```

### دانلود فایل

```python
# از temp-userfile (پیش‌فرض)
file_content = await storage.download_temp_file(object_key)

# از advisor-docs
file_content = await storage.download_temp_file(
    object_key,
    bucket=storage.documents_bucket
)
```

---

## 🧪 تست اتصال

### اسکریپت‌های تست

1. **`/srv/test/test_minio_connection.sh`** - تست کامل با mc
2. **`/srv/test/test_minio_simple.py`** - تست Python با boto3

### اجرای تست

```bash
# تست با bash
cd /srv/test
chmod +x test_minio_connection.sh
./test_minio_connection.sh

# تست با Python
python3 test_minio_simple.py
```

---

## ⚠️ وضعیت فعلی

### مشکل: سرور MinIO در دسترس نیست

```bash
$ curl -sk https://storage.tejarat.chat:9000/minio/health/live
# خروجی: HTTP Code 000 (Connection Failed)
```

**علت احتمالی:**
- ✅ تنظیمات در `.env` صحیح است
- ✅ کد به‌روز شده
- ❌ سرور MinIO خاموش است یا در دسترس نیست
- ❌ فایروال مسدود کرده
- ❌ شبکه قطع است

**راه‌حل:**
1. بررسی وضعیت سرور MinIO
2. بررسی فایروال
3. بررسی اتصال شبکه
4. تست با IP به جای domain

---

## 📋 چک‌لیست راه‌اندازی

- [x] اضافه کردن تنظیمات باکت به `.env`
- [x] به‌روزرسانی `settings.py`
- [x] به‌روزرسانی `storage_service.py`
- [x] ایجاد اسکریپت‌های تست
- [ ] تست اتصال به MinIO (منتظر دسترسی به سرور)
- [ ] بررسی وجود باکت‌ها
- [ ] تست آپلود/دانلود

---

## 🚀 مراحل بعدی

1. **بررسی سرور MinIO:**
   ```bash
   # بررسی وضعیت
   systemctl status minio  # یا docker ps | grep minio
   
   # بررسی لاگ
   journalctl -u minio -f  # یا docker logs minio
   ```

2. **تست اتصال:**
   ```bash
   # با curl
   curl -sk https://storage.tejarat.chat:9000/minio/health/live
   
   # با mc
   mc alias set tejarat https://storage.tejarat.chat:9000 ACCESS_KEY SECRET_KEY
   mc ls tejarat
   ```

3. **ایجاد باکت‌ها (اگر وجود ندارند):**
   ```bash
   mc mb tejarat/advisor-docs
   mc mb tejarat/temp-userfile
   ```

4. **تست از RAG Core:**
   ```bash
   # راه‌اندازی RAG Core
   docker-compose up -d rag-core
   
   # بررسی لاگ
   docker logs rag-core | grep -i minio
   ```

---

## 📞 پشتیبانی

اگر مشکل ادامه دارد:
1. بررسی کنید سرور MinIO روشن است
2. بررسی کنید credentials صحیح است
3. بررسی کنید فایروال باز است
4. تست کنید با IP به جای domain

**مستندات MinIO:** https://min.io/docs/minio/linux/index.html
