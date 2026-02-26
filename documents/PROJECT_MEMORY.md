# حافظه پروژه RAG Core

این فایل شامل تاریخچه تصمیمات، اقدامات و نیت‌های توسعه‌دهنده است. هنگام کار با این پروژه، این فایل را بخوانید.

---

## 🎯 هدف کلی پروژه

یک سیستم RAG (Retrieval-Augmented Generation) برای پاسخ به سوالات حقوقی، مالیاتی و کسب‌وکار در زبان فارسی.

---

## 📁 ساختار کلیدی فایل‌ها

| فایل | توضیح |
|------|-------|
| `/srv/app/rag/pipeline.py` | خط لوله اصلی RAG |
| `/srv/app/config/prompts.py` | تمام prompt های سیستم (متمرکز) |
| `/srv/app/api/v1/endpoints/query.py` | endpoint اصلی پرسش |
| `/srv/app/api/v1/endpoints/query_utils.py` | توابع کمکی query |
| `/srv/app/llm/classifier.py` | دسته‌بندی سوالات کاربر |
| `/srv/app/services/file_analysis_service.py` | تحلیل فایل‌های آپلود شده |

---

## 🏷️ دسته‌بندی سوالات (Classification)

سیستم سوالات را به 5 دسته تقسیم می‌کند:

1. **invalid_no_file** - متن بی‌معنی بدون فایل
2. **invalid_with_file** - متن بی‌معنی با فایل
3. **general** - سوالات عمومی، غیرتخصصی
4. **business_no_file** - سوالات حقوقی/مالی بدون فایل
5. **business_with_file** - سوالات حقوقی/مالی با فایل

### قوانین مهم دسته‌بندی:
- سوال "این فایل چیه" → همیشه **general**
- جزوه/کتاب/تست → **general** (نه business)
- فقط قرارداد/صورتحساب/بیمه‌نامه → **business_with_file**

---

## 🔧 اصلاحات انجام شده

### 1. متمرکزسازی Prompt ها (دسامبر 2025)
- تمام prompt ها از فایل‌های مختلف به `prompts.py` منتقل شدند
- کلاس‌های جدید: `FileAnalysisPrompts`, `MemoryPrompts`, `QueryEnhancementPrompts`

### 2. ذخیره محتوای فایل در تاریخچه مکالمه
- **مشکل:** مدل در پیام‌های بعدی به محتوای فایل دسترسی نداشت
- **راه حل:** تابع `build_user_message_content()` در `query_utils.py`
- حداکثر 4000 کاراکتر از محتوای فایل در پیام کاربر ذخیره می‌شود

### 3. Refactor کردن Classification Prompt
- **مشکل:** prompt خیلی طولانی و تکراری بود
- **راه حل:** کاهش از ~3500 کاراکتر به ~1434 کاراکتر
- حفظ قوانین کلیدی، حذف تکرارها

### 4. Refactor کردن pipeline.py
- حذف import های تکراری داخلی
- انتقال prompt enhancement به `prompts.py`
- ساده‌سازی متدهای طولانی
- کاهش ~100 خط کد

---

## ⚠️ نکات مهم برای توسعه آینده

### هنگام تغییر prompt ها:
1. همه prompt ها در `/srv/app/config/prompts.py` هستند
2. هرگز prompt را مستقیم در کد ننویسید
3. محدودیت 3000 کاراکتر برای تحلیل فایل رعایت شود

### هنگام کار با فایل‌ها:
1. محتوای فایل باید در تاریخچه ذخیره شود (برای follow-up)
2. تصاویر به صورت `input_image` با URL به LLM ارسال می‌شوند
3. حداکثر 4000 کاراکتر از محتوا در تاریخچه ذخیره می‌شود

### هنگام کار با RAG:
1. `RAGPipeline` در `pipeline.py` است
2. از `RAGQuery` برای ساخت query استفاده کنید
3. `temporal_context` برای فیلتر قوانین بر اساس تاریخ

---

## 📋 TODO های باقی‌مانده

- [ ] بهبود دقت classifier برای موارد edge case
- [ ] اضافه کردن تست‌های واحد
- [ ] بهینه‌سازی عملکرد reranker
- [ ] اصلاح `datetime.utcnow()` در ۱۲ فایل باقی‌مانده (۴۷ مورد) — اولویت پایین

---

## 📝 یادداشت‌های جلسات

### جلسه آخر (دسامبر 2025)
- Refactor کامل `pipeline.py`
- Refactor کردن Classification Prompt
- اصلاح ذخیره محتوای فایل در تاریخچه مکالمه
- انتقال تمام prompt ها به `prompts.py`

### جلسه رفع باگ‌ها — فاز ۱ (فوریه ۲۰۲۶)
فیلدهای `tier`, `daily_query_limit`, `daily_query_count` از مدل `UserProfile` حذف شده بودند اما ارجاعات به آنها در کد باقی مانده بود.

| فایل | اصلاح |
|------|-------|
| `app/api/v1/endpoints/admin.py` | حذف endpoint `update_user_tier`، اصلاح raw SQL با `text()`، حذف فیلدهای ناموجود |
| `app/api/v1/endpoints/users.py` | حذف فیلدهای `tier`, `daily_query_limit`, `daily_query_count` از response |
| `app/tasks/user.py` | حذف task `calculate_user_tier`، اصلاح `update_user_statistics` |
| `app/tasks/__init__.py` | حذف task های ناموجود sync از `__all__` |
| `app/api/v1/endpoints/embedding.py` | اضافه کردن import `get_local_embedding_service` |
| `app/celery_app.py` | حذف beat schedule ناموجود `process_sync_queue` |

### جلسه رفع باگ‌ها — فاز ۲: معماری (فوریه ۲۰۲۶)

| تغییر | فایل‌ها | توضیح |
|-------|---------|-------|
| Event Loop → `asyncio.run()` | `tasks/user.py`, `tasks/cleanup.py`, `tasks/notifications.py` | رفع memory leak و سازگاری Python 3.10+ |
| `datetime.utcnow()` → `datetime.now(timezone.utc)` | فایل‌های task + `qdrant_service.py` | رفع deprecation Python 3.12+ |
| `QdrantClient` → `AsyncQdrantClient` | `app/services/qdrant_service.py` | رفع blocking I/O در FastAPI event loop |

**نکته مهم:** تمام تغییرات فقط پیاده‌سازی داخلی Core را تغییر دادند. هیچ API endpoint URL یا response format تغییر نکرد. سیستم‌های Ingest و Users تحت تأثیر قرار نگرفتند.

---
---

## 🔗 اتصال سیستم‌های خارجی به RAG Core — تجربیات و نکات مهم

> آخرین به‌روزرسانی: 2026-02-13

### قانون طلایی
- **سیستم مرکزی (RAG Core) مرجع اصلی تنظیمات است**
- سیستم‌های دیگر (Users System، Ingest System) باید خودشان را با سیستم مرکزی هماهنگ کنند
- هرگز JWT_SECRET_KEY سیستم مرکزی را برای هماهنگی با سیستم‌های دیگر تغییر ندهید

### معماری شبکه
| سرور | IP | نقش |
|------|-----|------|
| RAG Core (مرکزی) | `10.10.10.20:7001` | سیستم هوش مصنوعی و RAG |
| Users System (بکند/فرانت) | `10.10.10.30` | بکند Django + فرانت Next.js |
| MinIO/S3 | `10.10.10.50:9000` | ذخیره‌سازی فایل |

### JWT_SECRET_KEY — هماهنگی بین سیستم‌ها
- کلید JWT در `/srv/.env` خط `JWT_SECRET_KEY` تعریف شده
- Users System از `djangorestframework-simplejwt` استفاده می‌کند و باید همین کلید را داشته باشد
- RAG Core از `python-jose` برای verify استفاده می‌کند
- تنظیمات simplejwt در Users System باید شامل باشد:
  - `USER_ID_CLAIM = 'sub'`
  - `TOKEN_TYPE_CLAIM = 'type'`
  - `ALGORITHM = 'HS256'`

### TrustedHostMiddleware — مهم!
- فایل: `/srv/app/main.py`
- در حالت production، فقط IP های مجاز می‌توانند درخواست بفرستند
- IP های داخلی شبکه (`10.10.10.20`, `10.10.10.30`, `10.10.10.40`, `10.10.10.50`) اضافه شده‌اند
- اگر سرور جدیدی اضافه شد، IP آن باید به `allowed_hosts` در `main.py` اضافه شود

### مشکلات رایج و راه‌حل‌ها

#### 1. خطای 401 "Invalid authentication token"
- **علت**: JWT_SECRET_KEY سیستم خارجی با RAG Core یکسان نیست
- **رفع**: کلید JWT سیستم خارجی را با کلید RAG Core هماهنگ کنید (نه برعکس!)

#### 2. خطای 400 "Invalid host header"
- **علت**: IP سرور درخواست‌دهنده در `TrustedHostMiddleware` نیست
- **رفع**: IP را به `allowed_hosts` در `/srv/app/main.py` اضافه کنید

#### 3. خطای 307 Redirect
- **علت**: FastAPI trailing slash — درخواست به `/api/v1/query` به `/api/v1/query/` redirect می‌شود
- **رفع**: سیستم خارجی باید `follow_redirects=True` در httpx client داشته باشد

#### 4. خطای AttributeError: llm_fallback_api_key
- **علت**: بعد از refactor LLM1/LLM2، property های backward compatibility فراموش شده بود
- **رفع**: property های `llm_fallback_*` در `/srv/app/config/settings.py` اضافه شد
- **درس**: هنگام refactor، همیشه backward compatibility property ها را حفظ کنید

### تنظیمات Production
- `ENVIRONMENT="production"`, `DEBUG=false`, `RELOAD=false`
- بعد از RELOAD=false، تغییرات کد خودکار اعمال نمی‌شوند
- برای اعمال تغییرات:
  ```bash
  docker stop core-api && docker rm core-api
  cd /srv/deployment/docker && docker compose up -d --no-build core-api
  ```

---

## 📊 نتایج تست عملکرد LLM (فوریه 2026)

### خلاصه تست‌ها
- **تاریخ:** 2026-02-15
- **مدل‌های تست شده:** gpt-5-nano, gpt-4o-mini, gpt-5-mini, gpt-5.1, gpt-5.2
- **منابع:** OpenAI و GapGPT
- **گزارش کامل:** `/srv/LLM_Performance_Report.md`

### نتایج کلیدی

#### برای کلاسیفیکیشن (Classification)
- **بهترین مدل:** `gpt-4o-mini` از OpenAI
- **عملکرد:** 1387ms میانگین، 100% نرخ موفقیت
- **توصیه:** استفاده از gpt-4o-mini برای دسته‌بندی سوالات

#### برای سوالات عمومی (General Queries)
- **بهترین مدل:** `gpt-4o-mini` از OpenAI
- **عملکرد:** 3856ms میانگین، 95% نرخ موفقیت
- **جایگزین:** `gpt-5.1` از OpenAI (5992ms، 100% موفقیت)

#### مقایسه OpenAI vs GapGPT
- **سرعت:** GapGPT 5.9% سریعتر (6688ms vs 7082ms)
- **پایداری:** OpenAI قابل اعتمادتر (91% vs 79.3% نرخ موفقیت)
- **توصیه:** OpenAI برای production، GapGPT برای توسعه/تست

#### مدل‌های با مشکل
- ❌ `gpt-5-nano` (GapGPT): 66.7% نرخ موفقیت - timeout های مکرر
- ❌ `gpt-5-mini`: 80% نرخ موفقیت - مشکلات پایداری
- ❌ `gpt-5.2` (GapGPT): 55% نرخ موفقیت - بسیار ناپایدار

### تنظیمات فعلی سیستم
بر اساس نتایج تست، تنظیمات زیر توصیه می‌شود:
- **کلاسیفیکیشن:** gpt-4o-mini (OpenAI)
- **سوالات عمومی:** gpt-4o-mini یا gpt-5.1 (OpenAI)
- **سوالات تجاری (RAG):** gpt-5.1 یا gpt-4o-mini (OpenAI)

---

## 🚀 انتقال Reranker به سرور اختصاصی (فوریه 2026)

### مشکل قبلی
- سرویس reranker به صورت local در docker-compose اصلی اجرا می‌شد
- مصرف منابع بالا (4GB RAM + 1.5GB مدل)
- تداخل با سرویس‌های اصلی Core API

### راه‌حل پیاده‌سازی شده
**سرور اختصاصی Reranker:**
- IP: `10.10.10.60`
- Port: `8100`
- مدل: `BAAI/bge-reranker-v2-m3`
- Docker Compose مستقل

### تغییرات انجام شده

#### 1. پاکسازی سرور Core
- ✅ حذف container و image های reranker (آزادسازی ~6GB)
- ✅ حذف `/srv/deployment/services/reranker/`
- ✅ حذف تنظیمات reranker از `docker-compose.yml`
- ✅ پاک کردن Docker cache و volumes

#### 2. راه‌اندازی سرور Reranker
**فایل‌های deployment در `/srv/deployment/` روی سرور 10.10.10.60:**
- `Dockerfile` - Python 3.11 slim با FastAPI
- `docker-compose.yml` - تنظیمات container
- `main.py` - سرویس FastAPI با CrossEncoder
- `requirements.txt` - وابستگی‌ها
- `start.sh` - اسکریپت نصب خودکار (نصب Docker + build + health check)
- `test.sh` - تست سلامت و عملکرد
- `README.md` - مستندات کامل

#### 3. بروزرسانی Core API
**در `/srv/.env`:**
```bash
RERANKER_SERVICE_URL="http://10.10.10.60:8100"
```

**در `/srv/deployment/start.sh`:**
- اضافه شدن prompt برای دریافت IP سرور reranker از کاربر
- تست خودکار اتصال به reranker در حین نصب
- مقدار پیش‌فرض: `10.10.10.60:8100`

#### 4. تست و تایید
```bash
# Health Check
curl http://10.10.10.60:8100/health
# Response: {"status":"healthy","model":"BAAI/bge-reranker-v2-m3","model_loaded":true}

# Rerank Test
# Rerank score: 0.9998 برای متن مرتبط، 0.00002 برای نامرتبط
```

### مزایای معماری جدید
1. **جداسازی منابع:** Reranker روی سرور مستقل، بدون تداخل با Core
2. **مقیاس‌پذیری:** امکان upgrade مستقل هر سرویس
3. **قابلیت نگهداری:** مدیریت و monitoring آسان‌تر
4. **انعطاف‌پذیری:** امکان استفاده از GPU در آینده برای reranker
5. **بهینه‌سازی منابع:** Core API فضای بیشتری برای cache و processing

### نکات مهم
- Reranker باید قبل از Core API راه‌اندازی شود
- در صورت تغییر IP سرور reranker، فقط `.env` را بروزرسانی کنید
- برای نصب جدید، `start.sh` به صورت خودکار IP را می‌پرسد
- سرویس reranker مستقل است و نیازی به Core API ندارد

---

## 🔧 رفع مشکل CORS - دسترسی سرور کاربران (فوریه 2026)

### مشکل
سرور کاربران (Users System) نمی‌توانست از پورت 7001 سوال بپرسد. درخواست‌های CORS با خطا مواجه می‌شدند.

### علت
متغیر `CORS_ORIGINS` در `.env` تعریف نشده بود و لیست origins مجاز خالی بود.

### راه‌حل
1. **تغییر نوع فیلد در settings.py:**
   - از `cors_origins: List[str]` به `cors_origins: str`
   - تغییر validator از `mode="before"` به `mode="after"`
   - پارس رشته‌های جدا شده با کاما به لیست

2. **افزودن CORS_ORIGINS به .env:**
   ```bash
   CORS_ORIGINS=http://localhost:3001,http://10.10.10.30,http://10.10.10.30:3001,https://10.10.10.30
   ```

3. **تست موفقیت‌آمیز:**
   ```bash
   curl -i -X OPTIONS http://localhost:7001/api/v1/query/ \
     -H "Origin: http://10.10.10.30" \
     -H "Access-Control-Request-Method: POST"
   # Response: access-control-allow-origin: http://10.10.10.30
   ```

### فایل‌های تغییر یافته
- `/srv/app/config/settings.py` - اصلاح نوع و validator
- `/srv/.env` - افزودن CORS_ORIGINS

---

*این فایل را قبل از شروع هر کار بخوانید.*
