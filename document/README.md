# Core System - RAG Engine

سیستم Core مغز متفکر و موتور پردازشی پروژه RAG است که مسئول پردازش سوالات کاربران و تولید پاسخ‌های هوشمند با استفاده از اطلاعات موجود در سیستم است.

## معماری سیستم

### فناوری‌های استفاده شده
- **FastAPI**: فریمورک وب سریع و مدرن
- **Qdrant**: پایگاه داده برداری برای جستجوی معنایی
- **PostgreSQL + pgvector**: خواندن داده از سیستم ingest
- **Redis**: کش و صف پیام
- **Celery**: پردازش ناهمزمان
- **LangChain**: مدیریت LLM و RAG pipeline
- **Docker**: کانتینریزه‌سازی

## ویژگی‌ها

### 1. پردازش هوش مصنوعی
- **NLP & Semantic Search**: جستجوی معنایی در پایگاه داده برداری
- **Multi-LLM Support**: پشتیبانی از مدل‌های مختلف (GPT, Claude, Llama, مدل‌های ایرانی)
- **RAG Pipeline**: بازیابی و تولید پاسخ بر اساس اسناد
- **Re-ranking**: رتبه‌بندی مجدد نتایج برای بهبود دقت
- **Intent Recognition**: تشخیص قصد کاربر
- **Context Management**: مدیریت تاریخچه مکالمات

### 2. جستجوی پیشرفته
- **Hybrid Search**: ترکیب جستجوی برداری و keyword
- **Temporal Search**: جستجو بر اساس زمان
- **Fuzzy Matching**: جستجوی تقریبی
- **Voice Search**: تبدیل صدا به متن (Whisper)
- **Image Search**: OCR و استخراج متن از تصاویر

### 3. عملکرد و مقیاس‌پذیری
- **Multi-layer Caching**: Redis + In-memory cache
- **Horizontal Scaling**: قابلیت افزودن سرور
- **Load Balancing**: توزیع بار
- **Async Processing**: پردازش ناهمزمان با Celery
- **Connection Pooling**: مدیریت بهینه اتصالات

### 4. امنیت
- **JWT Authentication**: احراز هویت امن
- **Rate Limiting**: محدودسازی درخواست‌ها
- **Content Filtering**: فیلترینگ محتوای نامناسب
- **Encryption**: رمزنگاری داده‌ها
- **Audit Logging**: ثبت همه تغییرات

## API Endpoints

### Query Processing
- `POST /api/v1/query` - پردازش سوال کاربر
- `POST /api/v1/query/stream` - پاسخ streaming
- `POST /api/v1/feedback` - دریافت بازخورد

### User Management
- `GET /api/v1/users/{user_id}/profile` - پروفایل کاربر
- `GET /api/v1/users/{user_id}/history` - تاریخچه مکالمات
- `DELETE /api/v1/users/{user_id}/history` - پاک کردن تاریخچه

### Sync Management
- `POST /api/v1/sync/embeddings` - همگام‌سازی از pgvector
- `GET /api/v1/sync/status` - وضعیت همگام‌سازی

### Admin
- `GET /api/v1/admin/stats` - آمار سیستم
- `POST /api/v1/admin/cache/clear` - پاک کردن کش

## نصب و راه‌اندازی

### پیش‌نیازها
- Python 3.11+
- PostgreSQL 15+ با pgvector
- Redis 7+
- Qdrant 1.7+
- Docker & Docker Compose (اختیاری)

### نصب محلی
```bash
# Clone repository
cd core

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env file

# Initialize database
python scripts/init_db.py

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 7001
```

### نصب با Docker
```bash
# Build and run
docker-compose up --build
```

## ساختار پروژه
```
core/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py             # Configuration
│   ├── api/                  # API endpoints
│   ├── core/                 # Core business logic
│   ├── models/               # Database models
│   ├── services/             # Business services
│   ├── llm/                  # LLM integrations
│   ├── rag/                  # RAG pipeline
│   └── utils/                # Utilities
├── scripts/                  # Management scripts
├── tests/                    # Test files
├── docker/                   # Docker files
├── requirements.txt
└── docker-compose.yml
```

## محیط‌های اجرا
- **Development**: localhost:7001
- **Production**: Separate servers with load balancing

## License
Proprietary
