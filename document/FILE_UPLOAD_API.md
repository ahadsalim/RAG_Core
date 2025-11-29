# API آپلود و پردازش فایل

## خلاصه

سیستم RAG Core اکنون از آپلود و پردازش فایل‌ها همراه با سوالات کاربران پشتیبانی می‌کند. کاربران می‌توانند تا 5 فایل (تصاویر، PDF، یا فایل‌های متنی) را همراه با هر سوال ارسال کنند.

## قابلیت‌های جدید

### 1. پردازش فایل‌ها
- **تصاویر**: استخراج متن با OCR (Tesseract)
  - فرمت‌های پشتیبانی شده: JPG, PNG, GIF, BMP, WEBP, TIFF
  - پشتیبانی از زبان‌های فارسی و انگلیسی
  
- **اسناد PDF**: استخراج متن از فایل‌های PDF
  - استفاده از PyPDF2 و pdfplumber
  
- **فایل‌های متنی**: خواندن فایل‌های TXT
  - پشتیبانی از انکدینگ‌های مختلف (UTF-8, Windows-1256, etc.)

### 2. ذخیره‌سازی موقت
- فایل‌ها در MinIO/S3 ذخیره می‌شوند
- مدت زمان نگهداری: 24 ساعت (قابل تنظیم)
- پاک‌سازی خودکار فایل‌های منقضی شده هر ساعت

### 3. محدودیت‌ها
- حداکثر 5 فایل در هر درخواست
- حداکثر حجم هر فایل: 10 مگابایت
- فرمت‌های پشتیبانی شده: JPG, PNG, GIF, BMP, WEBP, TIFF, PDF, TXT

## نحوه استفاده

### 1. درخواست بدون فایل (روش قبلی)

```bash
curl -X POST "http://localhost:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "query=قانون مدنی در مورد مالکیت چه می‌گوید؟" \
  -F "language=fa" \
  -F "max_results=5"
```

### 2. درخواست با یک فایل

```bash
curl -X POST "http://localhost:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "query=این سند چه می‌گوید؟" \
  -F "language=fa" \
  -F "files=@/path/to/document.pdf"
```

### 3. درخواست با چند فایل

```bash
curl -X POST "http://localhost:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "query=این اسناد را تحلیل کن" \
  -F "language=fa" \
  -F "files=@/path/to/image1.jpg" \
  -F "files=@/path/to/document.pdf" \
  -F "files=@/path/to/text.txt"
```

### 4. استفاده با Python

```python
import requests

url = "http://localhost:7001/api/v1/query/"
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN"
}

# داده‌های فرم
data = {
    "query": "این اسناد را بررسی کن",
    "language": "fa",
    "max_results": 5,
    "use_cache": True,
    "use_reranking": True
}

# فایل‌ها
files = [
    ("files", ("document.pdf", open("document.pdf", "rb"), "application/pdf")),
    ("files", ("image.jpg", open("image.jpg", "rb"), "image/jpeg"))
]

response = requests.post(url, data=data, files=files, headers=headers)
result = response.json()

print(f"پاسخ: {result['answer']}")
print(f"منابع: {result['sources']}")
```

### 5. استفاده با JavaScript/TypeScript

```javascript
const formData = new FormData();
formData.append('query', 'این اسناد را بررسی کن');
formData.append('language', 'fa');
formData.append('max_results', '5');

// اضافه کردن فایل‌ها
const file1 = document.getElementById('file1').files[0];
const file2 = document.getElementById('file2').files[0];
formData.append('files', file1);
formData.append('files', file2);

const response = await fetch('http://localhost:7001/api/v1/query/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${jwtToken}`
  },
  body: formData
});

const result = await response.json();
console.log('پاسخ:', result.answer);
```

## پارامترهای API

### پارامترهای اجباری
- `query` (string): سوال کاربر

### پارامترهای اختیاری
- `conversation_id` (string): شناسه مکالمه برای ادامه گفتگو
- `language` (string): زبان سوال (پیش‌فرض: "fa")
- `max_results` (integer): تعداد نتایج (پیش‌فرض: 5)
- `filters` (JSON string): فیلترهای جستجو
- `use_cache` (boolean): استفاده از کش (پیش‌فرض: true)
- `use_reranking` (boolean): استفاده از reranking (پیش‌فرض: true)
- `user_preferences` (JSON string): تنظیمات کاربر
- `files` (array): آرایه‌ای از فایل‌ها (حداکثر 5)

## پاسخ API

```json
{
  "answer": "بر اساس اسناد ارسالی، ...",
  "sources": ["doc-id-1", "doc-id-2"],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 250,
  "processing_time_ms": 1500,
  "cached": false
}
```

## جریان پردازش

1. **دریافت درخواست**: API فایل‌ها و سوال را دریافت می‌کند
2. **اعتبارسنجی**: بررسی تعداد و حجم فایل‌ها
3. **پردازش فایل‌ها**:
   - تصاویر: OCR با Tesseract
   - PDF: استخراج متن با PyPDF2/pdfplumber
   - TXT: خواندن مستقیم متن
4. **ذخیره‌سازی**: آپلود فایل‌ها به MinIO/S3
5. **ترکیب متن**: ترکیب متن استخراج شده با سوال کاربر
6. **پردازش RAG**: جستجو و تولید پاسخ
7. **ذخیره تاریخچه**: ذخیره مکالمه در دیتابیس
8. **برگرداندن پاسخ**: ارسال پاسخ به کاربر

## پیکربندی

### تنظیمات در `.env`

```bash
# OCR Settings
OCR_LANGUAGE=fas+eng
TESSERACT_CMD=/usr/bin/tesseract
MAX_IMAGE_SIZE_MB=10

# S3/MinIO Settings
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=core-storage
S3_REGION=us-east-1
S3_USE_SSL=false
```

## وظایف پس‌زمینه (Celery)

### پاک‌سازی خودکار فایل‌ها
- **نام Task**: `cleanup_expired_temp_files`
- **زمان‌بندی**: هر ساعت در دقیقه 30
- **عملکرد**: حذف فایل‌های منقضی شده (بیش از 24 ساعت)

```python
# اجرای دستی
from app.tasks.cleanup_files import cleanup_expired_temp_files
result = cleanup_expired_temp_files.delay()
```

## نکات امنیتی

1. **محدودیت حجم**: حداکثر 10MB برای هر فایل
2. **محدودیت تعداد**: حداکثر 5 فایل در هر درخواست
3. **اعتبارسنجی نوع فایل**: فقط فرمت‌های مجاز پذیرفته می‌شوند
4. **احراز هویت**: نیاز به JWT token معتبر
5. **انقضای خودکار**: فایل‌ها بعد از 24 ساعت حذف می‌شوند

## خطاها و رفع مشکل

### خطای 400: Maximum 5 files allowed
- **علت**: ارسال بیش از 5 فایل
- **راه‌حل**: تعداد فایل‌ها را کاهش دهید

### خطای 400: File size exceeds maximum
- **علت**: حجم فایل بیش از 10MB
- **راه‌حل**: حجم فایل را کاهش دهید

### خطای 400: Unsupported file type
- **علت**: فرمت فایل پشتیبانی نمی‌شود
- **راه‌حل**: از فرمت‌های پشتیبانی شده استفاده کنید

### خطای 429: Daily query limit exceeded
- **علت**: محدودیت روزانه کاربر
- **راه‌حل**: منتظر بمانید یا ارتقای tier

## تست

اجرای تست‌های API:

```bash
cd /srv
python test/test_file_upload_api.py
```

## مثال‌های کاربردی

### 1. پردازش قرارداد
```python
files = [("files", ("contract.pdf", open("contract.pdf", "rb"), "application/pdf"))]
data = {"query": "شرایط این قرارداد چیست؟", "language": "fa"}
response = requests.post(url, data=data, files=files, headers=headers)
```

### 2. تحلیل تصویر سند
```python
files = [("files", ("document.jpg", open("document.jpg", "rb"), "image/jpeg"))]
data = {"query": "این سند چه اطلاعاتی دارد؟", "language": "fa"}
response = requests.post(url, data=data, files=files, headers=headers)
```

### 3. مقایسه چند سند
```python
files = [
    ("files", ("doc1.pdf", open("doc1.pdf", "rb"), "application/pdf")),
    ("files", ("doc2.pdf", open("doc2.pdf", "rb"), "application/pdf"))
]
data = {"query": "تفاوت این دو سند چیست؟", "language": "fa"}
response = requests.post(url, data=data, files=files, headers=headers)
```

## پشتیبانی

برای مشکلات و سوالات:
- مستندات: `/srv/document/`
- لاگ‌ها: بررسی لاگ‌های سرور و Celery
- تست: اجرای `/srv/test/test_file_upload_api.py`
