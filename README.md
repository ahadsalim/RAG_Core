# 🚀 Core RAG System

سیستم مرکزی - مغز هوش مصنوعی پروژه RAG برای پاسخگویی هوشمند به سوالات حقوقی و کسب‌وکار

## 📋 فهرست

- [معرفی](#معرفی)
- [ویژگی‌ها](#ویژگیها)
- [نصب سریع](#نصب-سریع)
- [ساختار پروژه](#ساختار-پروژه)
- [API Endpoints](#api-endpoints)
- [پورت‌ها](#پورتها)

## معرفی

سیستم Core یک پلتفرم RAG (Retrieval-Augmented Generation) کامل است که:
- جستجوی معنایی در پایگاه دانش حقوقی با Qdrant
- تولید پاسخ با LLM (OpenAI با fallback به GapGPT)
- دسته‌بندی هوشمند سوالات (general, business, invalid)
- مدیریت مکالمات و حافظه بلندمدت کاربران
- جستجوی وب برای سوالات عمومی و تکمیل RAG
- همگام‌سازی با سیستم Ingest

## ویژگی‌ها

### 🎯 ویژگی‌های اصلی
- ✅ RAG Pipeline کامل با Qdrant Vector Database
- ✅ Multi-LLM با Fallback (OpenAI → GapGPT)
- ✅ Query Classification (general, business, invalid)
- ✅ Web Search برای سوالات عمومی
- ✅ Long-term Memory برای کاربران
- ✅ Conversation History
- ✅ File Analysis (PDF, Word, Images)
- ✅ Redis Cache برای سرعت بیشتر

### 🛡️ امنیت
- JWT Authentication
- API Key Verification
- Rate Limiting
- Input Validation

### 📊 مانیتورینگ
- Structured Logging (structlog)
- Health Checks
- Celery Task Monitoring (Flower)

## نصب سریع

### روش 1: اسکریپت خودکار (توصیه می‌شود)

```bash
cd /home/ahad/project/core/deployment

# انتخاب محیط و نصب خودکار
./start.sh
```

این اسکریپت از شما می‌پرسد:
1. محیط Development یا Production؟
2. API Keys را تنظیم می‌کند
3. همه چیز را به طور خودکار نصب می‌کند

### روش 2: نصب دستی با Docker Compose

```bash
# 1. تنظیم environment
cp deployment/config/.env.example .env
nano .env  # اضافه کردن API keys

# 2. اجرا با Docker Compose
cd deployment/docker
docker-compose up -d

# 3. بررسی وضعیت
docker-compose ps
```

## ساختار پروژه

```
core/
├── deployment/              # 🚀 اسکریپت‌های نصب
│   ├── start.sh            # اسکریپت شروع سریع
│   ├── manage.sh           # مدیریت سرویس‌ها
│   ├── backup.sh           # مدیریت backup/restore
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile
│   └── config/
│       └── .env.example
│
├── app/                     # 💻 کد اصلی برنامه
│   ├── api/v1/endpoints/   # API endpoints (query, users, sync, admin, memory)
│   ├── core/               # Security & dependencies
│   ├── db/                 # Database session management
│   ├── llm/                # LLM providers (OpenAI, factory, classifier)
│   ├── models/             # SQLAlchemy models (user, conversation)
│   ├── rag/                # RAG pipeline
│   ├── services/           # Business services (qdrant, embedding, memory, storage)
│   ├── tasks/              # Celery tasks (sync, cleanup, notifications)
│   └── config/             # Settings & prompts
│
├── document/                # 📚 مستندات
│
├── tools/                   # 🔧 ابزارهای نگهداری و مدیریت
│   ├── check_qdrant_data.py
│   ├── cleanup_orphan_conversations.py
│   ├── monitor_sync.sh
│   ├── reset_qdrant_collection.py
│   ├── verify_after_sync.py
│   └── verify_e5_large_migration.py
│
├── test/                    # 🧪 تست‌ها
│
├── alembic/                 # 🗄️ Database migrations
│
└── README.md               # این فایل
```

## API Endpoints

### 🎯 Endpoints اصلی

| Endpoint | توضیحات |
|----------|---------|
| `POST /api/v1/query/` | ارسال سوال و دریافت پاسخ |
| `GET /api/v1/users/me` | اطلاعات کاربر جاری |
| `GET /api/v1/memory/` | حافظه بلندمدت کاربر |
| `POST /api/v1/sync/trigger` | همگام‌سازی با Ingest |
| `GET /api/v1/admin/stats` | آمار سیستم |
| `GET /health` | Health Check |

### 🎯 مستندات API

پس از اجرا در دسترس است (در حالت debug):
- **Swagger UI**: http://localhost:7001/docs
- **ReDoc**: http://localhost:7001/redoc

## پورت‌ها

پورت‌ها طوری تنظیم شده‌اند که با سیستم Ingest تداخل نداشته باشند:

| سرویس | پورت | توضیحات |
|--------|------|----------|
| **Core API** | 7001 | API اصلی |
| **PostgreSQL** | 7433 | Database |
| **Redis** | 7379 | Cache & Queue |
| **Qdrant** | 7333 | Vector DB (HTTP) |
| **Qdrant gRPC** | 7334 | Vector DB (gRPC) |
| **Flower** | 7555 | Celery Monitoring |

## استفاده

### 🎮 رابط تست

یک رابط کاربری ساده برای تست:
```bash
# باز کردن در مرورگر
firefox /home/ahad/project/users/index.html
```

### 💻 API Examples

```bash
# Health Check
curl http://localhost:7001/health

# ارسال Query
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "حقوق کارگر چقدر است؟",
    "language": "fa",
    "max_results": 5
  }'

# مشاهده آمار
curl http://localhost:7001/api/v1/admin/stats \
  -H "X-API-Key: YOUR_API_KEY"
```

## مدیریت سیستم

### 📦 Backup & Restore

```bash
cd /home/ahad/project/core/deployment

# مدیریت backup/restore
./backup.sh
```

### 📊 مانیتورینگ

```bash
# مشاهده لاگ‌ها
docker-compose -f deployment/docker/docker-compose.yml logs -f core-api

# وضعیت سرویس‌ها
docker-compose -f deployment/docker/docker-compose.yml ps

# استفاده از منابع
docker stats
```

### 🔄 مدیریت

```bash
# Start
docker-compose -f deployment/docker/docker-compose.yml up -d

# Stop
docker-compose -f deployment/docker/docker-compose.yml down

# Restart
docker-compose -f deployment/docker/docker-compose.yml restart

# Rebuild
docker-compose -f deployment/docker/docker-compose.yml up -d --build
```

## یکپارچه‌سازی با Ingest

تغییرات لازم در سیستم Ingest **اعمال شده است**:

✅ فایل‌های API اضافه شده
✅ Migration ایجاد شده
✅ Celery tasks پیکربندی شده
✅ اسکریپت تست ایجاد شده

### مراحل فعال‌سازی در Ingest:

```bash
cd /home/ahad/project/ingest

# 1. اجرای migration
python manage.py migrate embeddings

# 2. تنظیم .env
# اضافه کردن CORE_API_URL و CORE_API_KEY

# 3. ایجاد read-only user در PostgreSQL
# (دستورات در CORE_INTEGRATION_APPLIED.md)

# 4. تست ارتباط
python deployment/test_core_connection.py
```

📄 **جزئیات کامل**: `/home/ahad/project/ingest/CORE_INTEGRATION_APPLIED.md`

## تنظیمات API Keys

### 🔑 کلیدهای مورد نیاز

```bash
# در فایل .env
OPENAI_API_KEY=sk-...           # ضروری
ANTHROPIC_API_KEY=sk-ant-...    # اختیاری
COHERE_API_KEY=...              # اختیاری (برای reranking)
JWT_SECRET_KEY=...              # تولید خودکار در production
```

### دریافت API Keys

- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com
- **Cohere**: https://dashboard.cohere.ai

📖 **راهنمای کامل**: [document/API_KEYS_SETUP.md](document/API_KEYS_SETUP.md)

## عیب‌یابی

### مشکلات رایج

**1. API آفلاین است**
```bash
# بررسی وضعیت
docker-compose -f deployment/docker/docker-compose.yml ps

# مشاهده لاگ‌ها
docker-compose -f deployment/docker/docker-compose.yml logs core-api
```

**2. خطای CORS**
```python
# در app/main.py
allow_origins=["*"]  # برای development
```

**3. Database متصل نمی‌شود**
```bash
# تست دسترسی
docker exec -it postgres-core psql -U core_user -d core_db -c "SELECT 1"
```

**4. Qdrant در دسترس نیست**
```bash
# بررسی Qdrant
curl http://localhost:7333/health
docker-compose logs qdrant
```

## توسعه

### اضافه کردن LLM Provider جدید

1. ایجاد فایل در `app/llm/your_provider.py`
2. پیاده‌سازی `BaseLLM`
3. اضافه کردن به config

### اضافه کردن API Endpoint

1. ایجاد فایل در `app/api/v1/endpoints/`
2. اضافه کردن router به `api.py`

## مشارکت

برای گزارش مشکلات یا پیشنهادات:
- Issues: در Git repository
- Documentation: در پوشه `document/`

## لایسنس

[در اینجا لایسنس پروژه را مشخص کنید]

---

## 🎯 Quick Links

- 🔑 [تنظیم API Keys](document/API_KEYS_SETUP.md)
- 🔗 [یکپارچه‌سازی Ingest](document/INGEST_INTEGRATION_GUIDE.md)
- 👥 [راهنمای Users](document/USERS_SYSTEM_NOTES.md)
- 💾 [Backup & Restore](deployment/backup.sh)

---

**نسخه**: 1.1.0  
**آخرین بروزرسانی**: دسامبر 2024  