# 🚀 Core RAG System

سیستم مرکزی - مغز هوش مصنوعی پروژه RAG برای پاسخگویی هوشمند به سوالات حقوقی

## 📋 فهرست

- [معرفی](#معرفی)
- [ویژگی‌ها](#ویژگیها)
- [نصب سریع](#نصب-سریع)
- [ساختار پروژه](#ساختار-پروژه)
- [مستندات](#مستندات)
- [پورت‌ها](#پورتها)

## معرفی

سیستم Core یک پلتفرم RAG (Retrieval-Augmented Generation) کامل است که:
- جستجوی معنایی در پایگاه دانش حقوقی
- تولید پاسخ با LLM (OpenAI, Anthropic)
- مدیریت مکالمات و تاریخچه کاربران
- همگام‌سازی با سیستم Ingest

## ویژگی‌ها

### 🎯 ویژگی‌های اصلی
- ✅ RAG Pipeline کامل با Qdrant
- ✅ Multi-LLM Support (OpenAI, Anthropic, Local)
- ✅ Hybrid Search (Vector + Keyword)
- ✅ Re-ranking با Cohere
- ✅ Semantic Cache برای سرعت بیشتر
- ✅ User Management & Authentication
- ✅ Conversation History
- ✅ API-First Architecture

### 🛡️ امنیت
- JWT Authentication
- API Key Verification
- Rate Limiting
- Input Validation
- Audit Logging

### 📊 مانیتورینگ
- Prometheus Metrics
- Structured Logging
- Health Checks
- Admin Dashboard

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

### روش 2: نصب دستی

```bash
# 1. تنظیم environment
cp deployment/config/.env.example .env
nano .env  # اضافه کردن API keys

# 2. Development
./deployment/deploy_development.sh

# 3. Production
sudo ./deployment/deploy_production.sh
```

## ساختار پروژه

```
core/
├── deployment/              # 🚀 اسکریپت‌های نصب
│   ├── start.sh            # اسکریپت شروع سریع
│   ├── backup_manager.sh   # مدیریت backup/restore
│   ├── deploy_development.sh
│   ├── deploy_production.sh
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile
│   └── config/
│       └── .env.example
│
├── app/                     # 💻 کد اصلی برنامه
│   ├── api/                # API endpoints
│   ├── core/               # Security & dependencies
│   ├── db/                 # Database management
│   ├── llm/                # LLM providers
│   ├── models/             # SQLAlchemy models
│   ├── rag/                # RAG pipeline
│   ├── services/           # Business services
│   └── utils/              # Utilities
│
├── document/                # 📚 مستندات
│   ├── API_KEYS_SETUP.md
│   ├── INGEST_INTEGRATION_GUIDE.md
│   └── USERS_SYSTEM_NOTES.md
│
├── scripts/                 # 🔧 ابزارها
│   └── init_db.py
│
├── alembic/                 # 🗄️ Database migrations
│
└── README.md               # این فایل
```

## مستندات

### 📖 مستندات اصلی

| فایل | توضیحات |
|------|---------|
| **[QUICK_START.md](QUICK_START.md)** | شروع سریع در 5 دقیقه |
| **[document/API_KEYS_SETUP.md](document/API_KEYS_SETUP.md)** | راهنمای تنظیم API Keys |
| **[document/INGEST_INTEGRATION_GUIDE.md](document/INGEST_INTEGRATION_GUIDE.md)** | یکپارچه‌سازی با Ingest |
| **[document/USERS_SYSTEM_NOTES.md](document/USERS_SYSTEM_NOTES.md)** | راهنمای سیستم Users |

### 🎯 مستندات API

پس از اجرا در دسترس است:
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

# مدیریت backup/restore با منوی تعاملی
./backup_manager.sh
```

گزینه‌های موجود:
1. Create Manual Backup
2. Restore from Backup
3. Setup Automated Backup
4. View Backups
5. Cleanup Old Backups
6. Setup Remote Backup Server
7. Test Backup System
8. Export/Import Configuration

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

- 📖 [راهنمای شروع سریع](QUICK_START.md)
- 🔑 [تنظیم API Keys](document/API_KEYS_SETUP.md)
- 🔗 [یکپارچه‌سازی Ingest](document/INGEST_INTEGRATION_GUIDE.md)
- 👥 [راهنمای Users](document/USERS_SYSTEM_NOTES.md)
- 💾 [Backup & Restore](deployment/backup_manager.sh)
- 🧪 [Test UI](../users/index.html)

---

**نسخه**: 1.0.0  
**آخرین بروزرسانی**: نوامبر 2024  
**وضعیت**: ✅ آماده برای Production
