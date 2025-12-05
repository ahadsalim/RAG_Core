# 📚 مستندات سیستم RAG Core

**نسخه:** 2.0.0  
**آخرین به‌روزرسانی:** 2025-12-05

---

## 📖 فهرست مستندات

### 1️⃣ مستندات سیستم مرکزی (Core)
**فایل:** `1_CORE_SYSTEM_DOCUMENTATION.md`

**محتوا:**
- معماری کامل سیستم
- نصب و راه‌اندازی
- پیکربندی و تنظیمات
- Celery و Background Tasks
- عیب‌یابی و مانیتورینگ

**مخاطب:** تیم توسعه Core، DevOps

---

### 2️⃣ راهنمای یکپارچه‌سازی سیستم Ingest
**فایل:** `2_INGEST_SYSTEM_API_GUIDE.md`

**محتوا:**
- API Endpoints برای همگام‌سازی
- فرمت داده‌ها و Embeddings
- الزامات امبدینگ (multilingual-e5-large, 1024 بُعد)
- Batch Processing و Error Handling
- نمونه کدهای Python

**مخاطب:** تیم Ingest

---

### 3️⃣ راهنمای یکپارچه‌سازی سیستم Users
**فایل:** `3_USERS_SYSTEM_API_GUIDE.md`

**محتوا:**
- API Endpoints برای Query Processing
- مدیریت کاربران و Conversations
- **جدید:** پشتیبانی از فایل‌های ضمیمه (MinIO)
- **جدید:** حافظه مکالمات (کوتاه‌مدت و بلندمدت)
- **جدید:** تحلیل فایل با LLM
- Rate Limiting و Caching
- Streaming Responses
- نمونه کدهای Python و JavaScript

**مخاطب:** تیم Users

---

### 4️⃣ مسئولیت‌های زیرسیستم‌ها
**فایل:** `4_SUBSYSTEMS_RESPONSIBILITIES.md`

**محتوا:**
- تقسیم مسئولیت‌ها بین Core، Ingest، Users
- نقاط ارتباطی و API Contract
- معماری کلی سیستم

**مخاطب:** همه تیم‌ها

---

### 5️⃣ راهنمای API استریم
**فایل:** `5_STREAMING_API_GUIDE.md`

**محتوا:**
- Server-Sent Events (SSE) format
- انواع پیام‌ها (status, token, done, error)
- نمونه کد JavaScript، React، Vue.js
- مقایسه با API عادی

**مخاطب:** تیم Frontend

---

## 🚀 شروع سریع

### برای تیم Core
```bash
cd /srv/deployment
sudo ./deploy.sh
```

### برای تیم Ingest
```bash
# مطالعه مستندات
cat /srv/document/2_INGEST_SYSTEM_API_GUIDE.md

# ارسال داده
curl -X POST http://rag-core:7001/api/v1/sync/embeddings \
  -H "X-Sync-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d @data.json
```

### برای تیم Users
```bash
# مطالعه مستندات
cat /srv/document/3_USERS_SYSTEM_API_GUIDE.md

# ارسال Query ساده
curl -X POST http://rag-core:7001/api/v1/query/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "سوال شما", "conversation_id": "uuid"}'

# ارسال Query با فایل
curl -X POST http://rag-core:7001/api/v1/query/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "این سند را بررسی کن",
    "file_attachments": [{
      "filename": "doc.pdf",
      "minio_url": "temp_uploads/user123/file.pdf",
      "file_type": "application/pdf"
    }]
  }'
```

---

## ⚙️ تنظیمات مهم

### Embedding Model
- **Model:** `intfloat/multilingual-e5-large`
- **Dimensions:** 1024
- **Type:** Local (در Core اجرا می‌شود)

### LLM
- **Provider:** OpenAI-Compatible
- **Model:** قابل تنظیم در `.env`
- **Base URL:** قابل تنظیم برای Local LLM

### Vector Database
- **Type:** Qdrant
- **Collection:** `documents`
- **Distance:** Cosine

### Rate Limiting
- **مدیریت:** سیستم کاربران (Users System)
- **توجه:** RAG Core فقط آمار استفاده را ذخیره می‌کند

---

## � عیب‌یابی

### مشکلات رایج

#### 1. خطای 504 Timeout
```bash
# غیرفعال کردن Query Classification
echo "ENABLE_QUERY_CLASSIFICATION=false" >> .env
docker-compose restart rag-core
```

#### 2. خطای Embedding
```bash
# بررسی لاگ
docker logs rag-core | grep -i embedding
```

#### 3. خطای MinIO
```bash
# بررسی اتصال
curl http://minio-server:9000/minio/health/live
```

---

## 📞 پشتیبانی

- **Core Issues:** Backend Team
- **Ingest Issues:** Data Team  
- **Users Issues:** Frontend Team

---

## 📝 تغییرات نسخه 2.0.0

### قابلیت‌های جدید
- ✅ **تحلیل فایل با LLM** - تحلیل هوشمند فایل‌های ضمیمه
- ✅ **حافظه کوتاه‌مدت** - 10 پیام آخر مکالمه
- ✅ **حافظه بلندمدت** - خلاصه‌سازی خودکار مکالمات
- ✅ **پشتیبانی فایل** - تصویر (OCR)، PDF، TXT
- ✅ **کلاسیفیکیشن با Context** - دسته‌بندی هوشمندتر سوالات

### بهبودها
- ✅ پردازش OCR فارسی و انگلیسی
- ✅ Timeout برای Classification (5 ثانیه)
- ✅ امکان غیرفعال کردن Classification
- ✅ مستندات کامل و به‌روز
