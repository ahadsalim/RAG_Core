# خلاصه پیاده‌سازی سیستم Core

## وضعیت پروژه

### ✅ کامل شده

1. **ساختار پروژه**
   - معماری FastAPI با best practices
   - ساختار مدولار و قابل توسعه
   - Docker و Docker Compose

2. **پایگاه داده**
   - مدل‌های SQLAlchemy (User, Conversation, Message, Cache)
   - Alembic migrations
   - PostgreSQL با asyncpg

3. **Vector Database**
   - Qdrant برای جستجوی برداری
   - پشتیبانی از ابعاد مختلف embedding
   - Hybrid search (vector + keyword)

4. **RAG Pipeline**
   - Retrieval از Qdrant
   - Query enhancement
   - Re-ranking
   - Response generation با LLM
   - Semantic cache

5. **LLM Integration**
   - OpenAI provider
   - قابلیت اضافه کردن provider های دیگر
   - Streaming support

6. **API Endpoints**
   - Query processing (`/api/v1/query`)
   - User management (`/api/v1/users`)
   - Sync management (`/api/v1/sync`)
   - Admin panel (`/api/v1/admin`)
   - Health checks

7. **Security**
   - JWT authentication
   - API key verification
   - Rate limiting
   - Input validation

8. **Caching**
   - Redis cache
   - Query cache در database
   - Semantic cache

## راه‌اندازی سریع

### محیط Development

```bash
# Clone و setup
cd /home/ahad/project/core

# ایجاد محیط مجازی
python -m venv venv
source venv/bin/activate

# نصب dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# ویرایش .env با مقادیر مناسب

# راه‌اندازی services با Docker
docker-compose up -d postgres-core redis-core qdrant

# ایجاد database
python scripts/init_db.py

# یا با Alembic
alembic upgrade head

# اجرای سرور
uvicorn app.main:app --reload --host 0.0.0.0 --port 7001
```

### محیط Production با Docker

```bash
# Build و اجرا
docker-compose up --build -d

# مشاهده logs
docker-compose logs -f core-api

# توقف
docker-compose down
```

## تست API

### 1. دریافت Token
```bash
# برای کاربر جدید
curl -X POST "http://localhost:7001/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: users_api_key" \
  -d '{
    "external_user_id": "user123",
    "username": "testuser",
    "tier": "premium"
  }'
```

### 2. ارسال Query
```bash
curl -X POST "http://localhost:7001/api/v1/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "حقوق ماهانه کارگر چقدر است؟",
    "language": "fa",
    "max_results": 5
  }'
```

### 3. Sync از Ingest
```bash
curl -X POST "http://localhost:7001/api/v1/sync/embeddings" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ingest_api_key" \
  -d '{
    "embeddings": [
      {
        "id": "emb1",
        "vector": [0.1, 0.2, ...],
        "text": "متن قانونی",
        "document_id": "doc1",
        "metadata": {}
      }
    ]
  }'
```

## نکات مهم Performance

1. **Database Optimization**
   - Connection pooling فعال
   - Indexes روی فیلدهای پرکاربرد
   - Async queries

2. **Caching Strategy**
   - Redis برای cache سریع
   - Query cache برای سوالات تکراری
   - TTL مناسب برای هر نوع cache

3. **Vector Search**
   - HNSW index در Qdrant
   - Batch processing برای embeddings
   - Hybrid search برای دقت بیشتر

4. **Scaling**
   - Horizontal scaling با multiple workers
   - Load balancing
   - Celery برای background tasks

## مانیتورینگ

- **Prometheus**: متریک‌ها در `/metrics`
- **Flower**: Celery monitoring در `http://localhost:7555`
- **Health Check**: `/health` و `/api/v1/admin/health/detailed`

## تغییرات مورد نیاز

### در سیستم Ingest
- مطابق فایل `INGEST_CHANGES.md`
- اضافه کردن sync endpoints
- ایجاد read-only user برای Core

### در سیستم Users
- مطابق فایل `USERS_SYSTEM_NOTES.md`
- پیاده‌سازی authentication flow
- مدیریت JWT tokens

## TODO (برای تکمیل)

1. **Testing**
   - Unit tests برای services
   - Integration tests برای API
   - Load testing

2. **Additional Features**
   - Voice search با Whisper
   - OCR برای تصاویر
   - WebSocket برای real-time
   - Multi-language LLM support

3. **Production**
   - SSL/TLS configuration
   - Backup strategy
   - Monitoring dashboard
   - CI/CD pipeline

## مستندات API

API documentation در:
- Swagger UI: `http://localhost:7001/docs`
- ReDoc: `http://localhost:7001/redoc`

## Security Checklist

- [ ] تغییر تمام رمزهای پیش‌فرض
- [ ] فعال کردن HTTPS در production
- [ ] تنظیم CORS origins
- [ ] Rate limiting configuration
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] Audit logging

## Contact & Support

برای سوالات و مشکلات:
1. بررسی logs: `docker-compose logs core-api`
2. Health check: `curl http://localhost:7001/health`
3. Admin panel: `/api/v1/admin/stats`
