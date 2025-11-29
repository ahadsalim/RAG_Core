# مستندات API - ارسال Query با فایل به RAG Core

## خلاصه

سیستم کاربران باید فایل‌ها را در MinIO آپلود کرده و `object_key` را همراه با query به RAG Core ارسال کند.

---

## Endpoint

```
POST http://rag-core:7001/api/v1/query/
Content-Type: application/json
Authorization: Bearer {JWT_TOKEN}
```

---

## Request Body

### ساختار کامل

```json
{
  "query": "سوال کاربر",
  "language": "fa",
  "max_results": 5,
  "conversation_id": "uuid-optional",
  "use_cache": true,
  "use_reranking": true,
  "file_attachments": [
    {
      "filename": "document.pdf",
      "minio_url": "temp_uploads/user123/20241129_120000_abc_document.pdf",
      "file_type": "application/pdf",
      "size_bytes": 1024000
    }
  ]
}
```

### فیلدها

| فیلد | نوع | اجباری | توضیح | مثال |
|------|-----|--------|-------|------|
| `query` | string | ✅ بله | سوال کاربر | "این سند چه می‌گوید؟" |
| `language` | string | خیر | زبان (fa/en/ar) | "fa" |
| `max_results` | integer | خیر | تعداد نتایج (1-20) | 5 |
| `conversation_id` | string | خیر | UUID مکالمه قبلی | "550e8400-..." |
| `use_cache` | boolean | خیر | استفاده از کش | true |
| `use_reranking` | boolean | خیر | استفاده از reranking | true |
| `file_attachments` | array | خیر | لیست فایل‌ها (حداکثر 5) | [...] |

### ساختار file_attachments

| فیلد | نوع | اجباری | توضیح |
|------|-----|--------|-------|
| `filename` | string | ✅ بله | نام اصلی فایل |
| `minio_url` | string | ✅ بله | object_key از MinIO |
| `file_type` | string | ✅ بله | MIME type |
| `size_bytes` | integer | خیر | حجم فایل |

---

## Response

### ساختار پاسخ

```json
{
  "answer": "پاسخ تولید شده...",
  "sources": ["doc-id-1", "doc-id-2"],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 250,
  "processing_time_ms": 1500,
  "cached": false,
  "files_processed": 1
}
```

### فیلدهای پاسخ

| فیلد | نوع | توضیح |
|------|-----|-------|
| `answer` | string | پاسخ تولید شده |
| `sources` | array | لیست منابع استفاده شده |
| `conversation_id` | string | UUID مکالمه |
| `message_id` | string | UUID پیام |
| `tokens_used` | integer | تعداد توکن مصرفی |
| `processing_time_ms` | integer | زمان پردازش (میلی‌ثانیه) |
| `cached` | boolean | آیا از کش بود؟ |
| `files_processed` | integer | تعداد فایل‌های پردازش شده |

---

## مثال‌های استفاده

### 1. Query بدون فایل

```bash
curl -X POST "http://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون مدنی در مورد مالکیت چه می‌گوید؟",
    "language": "fa",
    "max_results": 5
  }'
```

### 2. Query با یک فایل

```bash
curl -X POST "http://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "این سند چه می‌گوید؟",
    "language": "fa",
    "file_attachments": [
      {
        "filename": "document.pdf",
        "minio_url": "temp_uploads/user123/20241129_120000_abc_document.pdf",
        "file_type": "application/pdf"
      }
    ]
  }'
```

### 3. Query با چند فایل

```bash
curl -X POST "http://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "این اسناد را مقایسه کن",
    "language": "fa",
    "file_attachments": [
      {
        "filename": "doc1.pdf",
        "minio_url": "temp_uploads/user123/file1.pdf",
        "file_type": "application/pdf"
      },
      {
        "filename": "image.jpg",
        "minio_url": "temp_uploads/user123/file2.jpg",
        "file_type": "image/jpeg"
      }
    ]
  }'
```

---

## فرمت‌های فایل پشتیبانی شده

| نوع | فرمت‌ها | پردازش |
|-----|---------|---------|
| **تصاویر** | JPG, PNG, GIF, BMP, WEBP, TIFF | OCR (فارسی + انگلیسی) |
| **اسناد** | PDF | استخراج متن |
| **متن** | TXT | خواندن مستقیم |

---

## محدودیت‌ها

- ✅ حداکثر 5 فایل در هر درخواست
- ✅ حداکثر 10MB برای هر فایل
- ✅ فایل‌ها باید از قبل در MinIO آپلود شده باشند
- ✅ `minio_url` باید object_key معتبر باشد

---

## کدهای خطا

| کد | توضیح |
|----|-------|
| 200 | موفق |
| 400 | درخواست نامعتبر (بیش از 5 فایل، فرمت نامعتبر) |
| 401 | JWT token نامعتبر |
| 403 | دسترسی به مکالمه ندارید |
| 404 | فایل در MinIO یافت نشد |
| 429 | محدودیت روزانه تمام شد |
| 500 | خطای سرور |

---

## نکات مهم

### 1. مسیر object_key در MinIO

فرمت پیشنهادی:
```
temp_uploads/{user_id}/{timestamp}_{file_id}_{filename}
```

مثال:
```
temp_uploads/user123/20241129_120000_abc123_document.pdf
```

### 2. MIME Types رایج

```
application/pdf          → PDF
image/jpeg              → JPG
image/png               → PNG
text/plain              → TXT
```

### 3. مدیریت خطا

اگر فایلی در MinIO یافت نشد، RAG Core آن را skip می‌کند و با بقیه فایل‌ها ادامه می‌دهد.

---

## تنظیمات MinIO

### Environment Variables

```bash
# در سیستم کاربران و RAG Core یکسان باشد
S3_ENDPOINT_URL=http://minio-server:9000
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=shared-storage
S3_REGION=us-east-1
S3_USE_SSL=true
```

---

## جریان کار کامل

```
1. کاربر فایل را انتخاب می‌کند
   ↓
2. سیستم کاربران فایل را به MinIO آپلود می‌کند
   ↓
3. MinIO object_key را برمی‌گرداند
   ↓
4. سیستم کاربران query + object_key را به RAG Core می‌فرستد
   ↓
5. RAG Core فایل را از MinIO دانلود می‌کند
   ↓
6. RAG Core فایل را پردازش می‌کند (OCR/PDF extraction)
   ↓
7. RAG Core پاسخ را تولید و برمی‌گرداند
   ↓
8. سیستم کاربران پاسخ را به کاربر نمایش می‌دهد
```

---

## مثال کد Python

```python
import requests

# تنظیمات
RAG_CORE_URL = "http://rag-core:7001"
JWT_TOKEN = "your_jwt_token"

def send_query_with_files(query: str, minio_urls: list):
    """ارسال query با فایل‌ها به RAG Core."""
    
    # آماده‌سازی file_attachments
    file_attachments = []
    for url in minio_urls:
        file_attachments.append({
            "filename": url.split('/')[-1],  # استخراج نام فایل از URL
            "minio_url": url,
            "file_type": "application/pdf"  # یا تشخیص خودکار
        })
    
    # ارسال درخواست
    response = requests.post(
        f"{RAG_CORE_URL}/api/v1/query/",
        json={
            "query": query,
            "language": "fa",
            "max_results": 5,
            "file_attachments": file_attachments
        },
        headers={
            "Authorization": f"Bearer {JWT_TOKEN}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        return result['answer']
    else:
        raise Exception(f"Error: {response.status_code} - {response.text}")

# استفاده
answer = send_query_with_files(
    query="این سند چه می‌گوید؟",
    minio_urls=["temp_uploads/user123/file1.pdf"]
)
print(answer)
```

---

## مثال کد JavaScript

```javascript
async function sendQueryWithFiles(query, minioUrls) {
  const fileAttachments = minioUrls.map(url => ({
    filename: url.split('/').pop(),
    minio_url: url,
    file_type: 'application/pdf'
  }));

  const response = await fetch('http://rag-core:7001/api/v1/query/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query,
      language: 'fa',
      max_results: 5,
      file_attachments: fileAttachments
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const result = await response.json();
  return result.answer;
}

// استفاده
const answer = await sendQueryWithFiles(
  'این سند چه می‌گوید؟',
  ['temp_uploads/user123/file1.pdf']
);
console.log(answer);
```

---

## پشتیبانی

در صورت بروز مشکل:
1. بررسی کنید JWT token معتبر است
2. بررسی کنید object_key در MinIO وجود دارد
3. بررسی کنید فرمت فایل پشتیبانی می‌شود
4. لاگ‌های RAG Core را بررسی کنید

---

## تغییرات نسبت به نسخه قبل

- ✅ حذف آپلود مستقیم فایل
- ✅ استفاده از لینک MinIO (object_key)
- ✅ کاهش traffic شبکه
- ✅ سرعت بیشتر
- ✅ مدیریت بهتر فایل‌ها
