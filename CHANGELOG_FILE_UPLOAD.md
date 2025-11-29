# تغییرات: قابلیت آپلود و پردازش فایل

## تاریخ: 2024-11-29

## خلاصه
سیستم RAG Core اکنون از آپلود و پردازش همزمان تا 5 فایل (تصاویر، PDF، TXT) همراه با سوالات کاربران پشتیبانی می‌کند.

## فایل‌های جدید

### 1. سرویس‌ها
- **`/srv/app/services/file_processing_service.py`**
  - پردازش تصاویر با OCR (Tesseract)
  - استخراج متن از PDF (PyPDF2/pdfplumber)
  - خواندن فایل‌های متنی با پشتیبانی از انکدینگ‌های مختلف
  - پردازش همزمان چندین فایل

- **`/srv/app/services/storage_service.py`**
  - آپلود فایل‌ها به MinIO/S3
  - مدیریت فایل‌های موقت با expiration
  - دانلود و حذف فایل‌ها
  - پاک‌سازی خودکار فایل‌های منقضی شده

### 2. وظایف پس‌زمینه (Celery Tasks)
- **`/srv/app/tasks/cleanup_files.py`**
  - Task پاک‌سازی فایل‌های منقضی شده
  - اجرای خودکار هر ساعت

### 3. تست و مستندات
- **`/srv/test/test_file_upload_api.py`**
  - تست‌های API برای آپلود فایل
  - مثال‌های استفاده

- **`/srv/document/FILE_UPLOAD_API.md`**
  - مستندات کامل API
  - راهنمای استفاده
  - مثال‌های کاربردی

## فایل‌های اصلاح شده

### 1. API Endpoints
- **`/srv/app/api/v1/endpoints/query.py`**
  - تغییر signature endpoint از JSON به Form Data
  - اضافه شدن پارامتر `files` برای دریافت فایل‌ها
  - پردازش فایل‌ها قبل از ارسال به RAG pipeline
  - ترکیب متن استخراج شده با سوال کاربر
  - ذخیره metadata فایل‌ها در پیام‌ها

### 2. Dependencies
- **`/srv/deployment/requirements.txt`**
  - اضافه شدن `PyPDF2>=3.0.0`
  - اضافه شدن `pdfplumber>=0.10.0`
  - اضافه شدن `boto3>=1.34.0`

### 3. Celery Configuration
- **`/srv/app/celery_app.py`**
  - اضافه شدن route برای `cleanup_files` tasks
  - اضافه شدن schedule برای پاک‌سازی خودکار فایل‌ها

## قابلیت‌های جدید

### 1. پردازش فایل
- **تصاویر**: JPG, PNG, GIF, BMP, WEBP, TIFF
  - OCR با Tesseract
  - پشتیبانی از فارسی و انگلیسی
  
- **اسناد PDF**
  - استخراج متن با PyPDF2
  - Fallback به pdfplumber
  
- **فایل‌های متنی**: TXT
  - پشتیبانی از UTF-8, Windows-1256, ISO-8859-1, CP1252

### 2. ذخیره‌سازی
- آپلود به MinIO/S3 bucket
- Expiration خودکار بعد از 24 ساعت
- Metadata شامل user_id, filename, timestamps

### 3. محدودیت‌ها
- حداکثر 5 فایل در هر درخواست
- حداکثر 10MB برای هر فایل
- اعتبارسنجی نوع فایل

## تغییرات API

### قبل (JSON Request)
```json
POST /api/v1/query/
Content-Type: application/json

{
  "query": "سوال",
  "language": "fa",
  "max_results": 5
}
```

### بعد (Form Data with Files)
```bash
POST /api/v1/query/
Content-Type: multipart/form-data

query=سوال
language=fa
max_results=5
files=@file1.pdf
files=@file2.jpg
```

## جریان پردازش

```
1. دریافت درخواست (query + files)
   ↓
2. اعتبارسنجی (تعداد، حجم، نوع)
   ↓
3. پردازش فایل‌ها (OCR/PDF extraction)
   ↓
4. آپلود به MinIO/S3
   ↓
5. ترکیب متن با query
   ↓
6. پردازش RAG
   ↓
7. ذخیره در دیتابیس
   ↓
8. برگرداندن پاسخ
```

## پیکربندی مورد نیاز

### Environment Variables (.env)
```bash
# OCR
OCR_LANGUAGE=fas+eng
TESSERACT_CMD=/usr/bin/tesseract
MAX_IMAGE_SIZE_MB=10

# S3/MinIO
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=core-storage
S3_REGION=us-east-1
S3_USE_SSL=false
```

### نصب Dependencies
```bash
pip install -r deployment/requirements.txt
```

### نصب Tesseract (برای OCR)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-fas tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang
```

## استقرار (Deployment)

### 1. نصب Dependencies
```bash
cd /srv
pip install -r deployment/requirements.txt
```

### 2. راه‌اندازی MinIO
```bash
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"
```

### 3. راه‌اندازی Celery Worker
```bash
celery -A app.celery_app worker --loglevel=info -Q cleanup
```

### 4. راه‌اندازی Celery Beat
```bash
celery -A app.celery_app beat --loglevel=info
```

### 5. راه‌اندازی API Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

## تست

### اجرای تست‌ها
```bash
cd /srv
python test/test_file_upload_api.py
```

### تست دستی با curl
```bash
# تست با یک فایل
curl -X POST "http://localhost:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "query=این سند چه می‌گوید؟" \
  -F "language=fa" \
  -F "files=@document.pdf"

# تست با چند فایل
curl -X POST "http://localhost:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "query=این اسناد را تحلیل کن" \
  -F "files=@image1.jpg" \
  -F "files=@document.pdf" \
  -F "files=@text.txt"
```

## نکات مهم

### امنیت
- همه فایل‌ها نیاز به احراز هویت JWT دارند
- اعتبارسنجی نوع و حجم فایل
- فایل‌ها بعد از 24 ساعت خودکار حذف می‌شوند

### عملکرد
- پردازش همزمان فایل‌ها با ThreadPoolExecutor
- استفاده از async/await برای عملیات I/O
- کش کردن نتایج OCR (در صورت نیاز)

### مقیاس‌پذیری
- استفاده از MinIO/S3 برای ذخیره‌سازی توزیع شده
- Celery برای پردازش پس‌زمینه
- قابلیت افزودن worker های بیشتر

## مشکلات شناخته شده

1. **OCR Accuracy**: دقت OCR برای تصاویر با کیفیت پایین ممکن است کم باشد
   - راه‌حل: پیش‌پردازش تصویر قبل از OCR

2. **PDF Encryption**: PDF های رمزگذاری شده پشتیبانی نمی‌شوند
   - راه‌حل: کاربر باید رمز را بردارد

3. **Large Files**: فایل‌های بزرگ ممکن است زمان پردازش طولانی داشته باشند
   - راه‌حل: افزایش timeout یا پردازش async

## کارهای آینده

- [ ] پشتیبانی از فرمت‌های بیشتر (DOCX, XLSX, etc.)
- [ ] بهبود دقت OCR با پیش‌پردازش تصویر
- [ ] کش کردن نتایج پردازش فایل
- [ ] پشتیبانی از فایل‌های فشرده (ZIP, RAR)
- [ ] تشخیص خودکار زبان در OCR
- [ ] پیش‌نمایش فایل‌های آپلود شده
- [ ] آمار و گزارش استفاده از فایل‌ها

## مراجع

- [FastAPI File Upload](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [PyPDF2 Documentation](https://pypdf2.readthedocs.io/)
- [MinIO Python SDK](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [Celery Documentation](https://docs.celeryproject.org/)

## نویسنده
RAG Core Development Team

## نسخه
1.0.0 - Initial file upload support
