# 📚 مستندات سیستم RAG Core

**نسخه:** 2.0.0  
**آخرین به‌روزرسانی:** 2025-11-29

---

## 📄 فهرست مستندات اصلی

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
- Rate Limiting و Caching
- Streaming Responses
- نمونه کدهای Python و JavaScript

**مخاطب:** تیم Users

---

### 4️⃣ API ارسال Query با فایل (MinIO)
**فایل:** `API_DOCUMENTATION.md`

**محتوا:**
- ارسال Query همراه با فایل‌های ضمیمه
- استفاده از MinIO برای ذخیره فایل
- پردازش تصاویر (OCR) و PDF
- نمونه کدهای کامل
- عیب‌یابی و خطاهای رایج

**مخاطب:** تیم Users

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
cat /srv/document/API_DOCUMENTATION.md

# ارسال Query
curl -X POST http://rag-core:7001/api/v1/query/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "سوال شما"}'
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
- **Daily Limit:** 50 query per user
- **قابل تنظیم:** در `.env`

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

- ✅ اضافه شدن پشتیبانی از فایل‌های ضمیمه (MinIO)
- ✅ پردازش تصاویر با OCR (فارسی + انگلیسی)
- ✅ پردازش PDF و TXT
- ✅ بهبود Query Classification با Timeout
- ✅ امکان غیرفعال کردن Classification
- ✅ مستندات کامل API
