# 📚 مستندات سیستم RAG

این پوشه شامل تمام مستندات فنی سیستم RAG سه‌لایه است.

## 📄 فهرست مستندات

### 1️⃣ مستندات سیستم مرکزی (Core)
**فایل:** `1_CORE_SYSTEM_DOCUMENTATION.md`

مستندات کامل سیستم Core شامل:
- معماری و نصب
- پیکربندی و تنظیمات
- API Reference
- Celery و Background Tasks
- عیب‌یابی

**مخاطب:** تیم توسعه Core، DevOps

---

### 2️⃣ راهنمای یکپارچه‌سازی سیستم Ingest
**فایل:** `2_INGEST_SYSTEM_API_GUIDE.md`

راهنمای کامل برای تیم Ingest جهت ارسال داده به Core:
- API Endpoints برای همگام‌سازی
- فرمت داده‌ها و Embeddings
- الزامات امبدینگ (multilingual-e5-base, 768 بُعد)
- Batch Processing و Error Handling
- نمونه کدهای Python

**مخاطب:** تیم توسعه Ingest

---

### 3️⃣ راهنمای یکپارچه‌سازی سیستم Users
**فایل:** `3_USERS_SYSTEM_API_GUIDE.md`

راهنمای کامل برای تیم Users جهت ارتباط با Core:
- JWT Authentication
- Query Processing APIs
- Streaming Responses
- مدیریت مکالمات و تاریخچه
- User Tier Management
- نمونه کدهای Python و JavaScript

**مخاطب:** تیم توسعه Users (Frontend/Backend)

---

### 4️⃣ تقسیم وظایف بین زیرسیستم‌ها
**فایل:** `4_SUBSYSTEMS_RESPONSIBILITIES.md`

مستند معماری و تقسیم مسئولیت‌ها:
- نقش هر زیرسیستم
- جدول تفکیک وظایف
- Data Flow بین سیستم‌ها
- نکات مهم برای هر تیم

**مخاطب:** همه تیم‌ها، مدیران فنی، معماران

---

### 5️⃣ راهنمای پیکربندی Embedding
**فایل:** `EMBEDDING_CONFIGURATION_GUIDE.md`

راهنمای کامل تنظیم و استفاده از Embedding:
- API Mode vs Local Mode
- Auto-detection بر اساس .env
- مدل‌های پیشنهادی
- Migration و تغییر مدل
- هشدارها و Best Practices

**مخاطب:** DevOps، تیم Core، تیم Ingest

---

### 6️⃣ راهنمای تنظیمات LLM و ذخیره‌سازی داده
**فایل:** `LLM_CONFIGURATION_AND_DATA_STORAGE.md`

راهنمای جامع تنظیمات LLM و معماری ذخیره‌سازی:
- تنظیمات LLM برای بهبود کیفیت پاسخ
- تنظیمات RAG و Reranking
- ساختار ذخیره‌سازی چت و سوابق کاربر
- تقسیم مسئولیت بین Core و Users
- سناریوهای مختلف و تنظیمات پیشنهادی

**مخاطب:** همه تیم‌ها، Product Manager، DevOps

---

## 🎯 راهنمای سریع

### برای تیم Ingest:
```bash
# خواندن این فایل‌ها به ترتیب:
1. 4_SUBSYSTEMS_RESPONSIBILITIES.md  # درک کلی معماری
2. 2_INGEST_SYSTEM_API_GUIDE.md      # جزئیات فنی
```

### برای تیم Users:
```bash
# خواندن این فایل‌ها به ترتیب:
1. 4_SUBSYSTEMS_RESPONSIBILITIES.md           # درک کلی معماری
2. 3_USERS_SYSTEM_API_GUIDE.md                # جزئیات فنی
3. LLM_CONFIGURATION_AND_DATA_STORAGE.md      # ذخیره‌سازی داده
```

### برای تیم Core:
```bash
# خواندن این فایل‌ها:
1. 1_CORE_SYSTEM_DOCUMENTATION.md             # مستندات داخلی
2. 4_SUBSYSTEMS_RESPONSIBILITIES.md           # ارتباط با سایر سیستم‌ها
3. EMBEDDING_CONFIGURATION_GUIDE.md           # تنظیمات Embedding
4. LLM_CONFIGURATION_AND_DATA_STORAGE.md      # تنظیمات LLM
```

### برای DevOps:
```bash
# خواندن این فایل‌ها:
1. 1_CORE_SYSTEM_DOCUMENTATION.md             # نصب و راه‌اندازی
2. EMBEDDING_CONFIGURATION_GUIDE.md           # پیکربندی Embedding
3. LLM_CONFIGURATION_AND_DATA_STORAGE.md      # تنظیمات LLM
```

### برای Product Manager:
```bash
# خواندن این فایل‌ها:
1. 4_SUBSYSTEMS_RESPONSIBILITIES.md           # معماری کلی
2. LLM_CONFIGURATION_AND_DATA_STORAGE.md      # قابلیت‌ها و محدودیت‌ها
```

---

## 🔑 نکات مهم

### احراز هویت
- **Ingest → Core**: API Key در header `X-API-Key`
- **Users → Core**: JWT Token در header `Authorization: Bearer {token}`

### Endpoints اصلی
```
Core Base URL: https://core.domain.com

Ingest APIs:
  POST /api/v1/sync/embeddings
  GET  /api/v1/sync/status

Users APIs:
  POST /api/v1/query/
  POST /api/v1/query/stream
  GET  /api/v1/users/profile
```

### مدل Embedding
```
Model: intfloat/multilingual-e5-base
Dimensions: 768
Normalization: Required
```

---

## 📞 پشتیبانی

- **مستندات API:** https://core.domain.com/docs
- **Health Check:** https://core.domain.com/health
- **تیم Core:** core-team@domain.com

---

**آخرین بروزرسانی:** 2025-11-17
