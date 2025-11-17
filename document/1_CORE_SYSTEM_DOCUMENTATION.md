# مستندات کامل سیستم RAG Core

**نسخه:** 1.0.0  
**تاریخ:** 2025-11-15

---

## فهرست مطالب

1. [شروع سریع](#شروع-سریع)
2. [معماری سیستم](#معماری-سیستم)
3. [نصب و راه‌اندازی](#نصب-و-راهاندازی)
4. [پیکربندی](#پیکربندی)
5. [Celery و Background Tasks](#celery-و-background-tasks)
6. [یکپارچه‌سازی](#یکپارچهسازی)
7. [API Reference](#api-reference)
8. [عیب‌یابی](#عیبیابی)

---

## شروع سریع

### نصب با یک دستور

```bash
cd /srv/deployment
chmod +x deploy.sh
sudo ./deploy.sh
```

### دسترسی به سرویس‌ها

```bash
# API Documentation
http://localhost:7001/docs

# Health Check
http://localhost:7001/health

# Celery Monitoring (Flower)
http://localhost:5555

# Nginx Proxy Manager
http://localhost:81
```

### مدیریت سرویس‌ها

```bash
cd /srv/deployment/docker

# شروع
docker-compose up -d

# توقف
docker-compose stop

# مشاهده لاگ‌ها
docker-compose logs -f

# راه‌اندازی مجدد
docker-compose restart
```

---

## معماری سیستم

### نمای کلی

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│     Nginx Proxy Manager (SSL)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│          Core API (FastAPI)          │
│  ┌────────────────────────────────┐  │
│  │   Query Processing             │  │
│  │   User Management              │  │
│  │   Conversation Handling        │  │
│  └────────────────────────────────┘  │
└───┬────────┬────────┬────────┬───────┘
    │        │        │        │
    ▼        ▼        ▼        ▼
┌────────┐ ┌────┐ ┌──────┐ ┌────────┐
│Postgres│ │Redis│ │Qdrant│ │Celery  │
│  Core  │ │     │ │Vector│ │Workers │
└────────┘ └────┘ └──────┘ └────────┘
    │                 │
    ▼                 ▼
┌────────┐       ┌────────┐
│ Ingest │       │ Users  │
│ System │       │ System │
└────────┘       └────────┘
```

### جریان RAG (Retrieval-Augmented Generation)

```
1. User Query
   ↓
2. Query Embedding (via Ingest API)
   ↓
3. Vector Search (Qdrant)
   ↓
4. Context Retrieval
   ↓
5. LLM Processing (OpenAI/Anthropic)
   ↓
6. Response Generation
   ↓
7. Save to Database
   ↓
8. Return to User
```

### کامپوننت‌های اصلی

#### 1. Core API
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM برای PostgreSQL
- **Pydantic** - Validation
- **Structlog** - Logging

#### 2. Database Layer
- **PostgreSQL** - ذخیره کاربران، مکالمات، پیام‌ها
- **Redis** - Cache و session management
- **Qdrant** - Vector database برای embeddings

#### 3. Background Processing
- **Celery Worker** - پردازش async tasks
- **Celery Beat** - Scheduler برای taskهای دوره‌ای
- **Flower** - Monitoring UI

#### 4. External Services
- **Ingest System** - پردازش اسناد و embedding
- **Users System** - مدیریت کاربران و احراز هویت

---

## نصب و راه‌اندازی

### پیش‌نیازها

- Ubuntu 20.04+ یا Debian 11+
- Docker 20.10+
- Docker Compose 1.29+
- حداقل 4GB RAM
- حداقل 20GB فضای دیسک

### نصب کامل

```bash
# 1. Clone repository
git clone <repository-url> /srv
cd /srv

# 2. اجرای اسکریپت نصب
cd deployment
chmod +x deploy.sh
sudo ./deploy.sh
```

اسکریپت به صورت خودکار:
- Docker و Docker Compose را نصب می‌کند
- فایل `.env` با رمزهای امن ایجاد می‌کند
- تمام سرویس‌ها را راه‌اندازی می‌کند
- Systemd service برای auto-start تنظیم می‌کند

### بررسی نصب

```bash
# وضعیت سرویس‌ها
cd /srv/deployment/docker
docker-compose ps

# تست API
curl http://localhost:7001/health

# مشاهده لاگ‌ها
docker-compose logs -f core-api
```

---

## پیکربندی

### فایل .env

فایل اصلی تنظیمات در `/srv/.env`:

```bash
# محیط
ENVIRONMENT=production

# دامنه
DOMAIN_NAME=your-domain.com

# Database
DATABASE_URL=postgresql+asyncpg://core_user:PASSWORD@postgres-core:5432/core_db
POSTGRES_DB=core_db
POSTGRES_USER=core_user
POSTGRES_PASSWORD=secure-password

# Redis
REDIS_URL=redis://:PASSWORD@redis-core:6379/0
REDIS_PASSWORD=secure-password

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Celery
CELERY_BROKER_URL=redis://:PASSWORD@redis-core:6379/1
CELERY_RESULT_BACKEND=redis://:PASSWORD@redis-core:6379/2

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Ingest Integration
INGEST_API_URL=http://ingest-api:8000
INGEST_API_KEY=your-ingest-key

# Users Integration
USERS_API_URL=http://users-api:9000
USERS_API_KEY=your-users-key
```

### تنظیمات LLM

#### OpenAI
```bash
OPENAI_API_KEY=sk-...
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4-turbo-preview
```

#### Anthropic Claude
```bash
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-3-opus-20240229
```

#### Local Models (HuggingFace)
```bash
USE_LOCAL_LLM=true
LOCAL_LLM_MODEL=meta-llama/Llama-2-7b-chat-hf
HUGGINGFACE_TOKEN=hf_...
```

### پورت‌ها

#### سرویس‌های Core

| سرویس | پورت داخلی | پورت خارجی | توضیحات |
|-------|------------|------------|---------|
| Core API | 7001 | 7001 | FastAPI Application |
| PostgreSQL | 5432 | 7433 | Database (تغییر از 5432 برای جلوگیری از تداخل) |
| Redis | 6379 | 7379 | Cache & Queue (تغییر از 6379 برای جلوگیری از تداخل) |
| Qdrant HTTP | 6333 | 7333 | Vector Database HTTP |
| Qdrant GRPC | 6334 | 7334 | Vector Database GRPC |
| Flower | 5555 | 5555 | Celery Monitoring |
| Nginx | 80/443/81 | 80/443/81 | Proxy Manager |

#### سرویس‌های Ingest (برای اطلاع)

| سرویس | پورت |
|-------|------|
| Ingest API | 8000 |
| PostgreSQL Ingest | 5432 |
| Redis Ingest | 6379 |
| Elasticsearch | 9200 |

**نکته:** تمام پورت‌های Core طوری انتخاب شده‌اند که با سیستم Ingest تداخل نداشته باشند و می‌توانند روی یک سرور اجرا شوند.

---

## Celery و Background Tasks

### معماری Celery

```
┌──────────────┐
│ Core API     │ ──┐
└──────────────┘   │
                   ▼
              ┌─────────┐
              │  Redis  │ (Broker)
              └─────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Worker 1│ │Worker 2│ │Worker 3│
   └────────┘ └────────┘ └────────┘
        │          │          │
        └──────────┼──────────┘
                   ▼
              ┌─────────┐
              │  Redis  │ (Results)
              └─────────┘
```

### Tasks پیاده‌سازی شده

#### Sync Tasks (4 tasks)
```python
# همگام‌سازی embeddings از Ingest
sync_embeddings_task.delay(batch_size=100)

# پردازش صف همگام‌سازی (هر 5 دقیقه)
process_sync_queue.delay()

# همگام‌سازی کامل
trigger_full_sync_task.delay()

# حذف embeddings یک سند
delete_document_embeddings_task.delay(document_id)
```

#### Notification Tasks (3 tasks)
```python
# ارسال نتیجه query به Users
send_query_result_to_users.delay(
    user_id, conversation_id, message_id,
    query, answer, sources, tokens_used
)

# ارسال آمار ساعتی (خودکار)
send_usage_statistics.delay()

# ارسال اعلان سیستمی
send_system_notification.delay(
    notification_type, title, message, user_ids
)
```

#### Cleanup Tasks (4 tasks)
```python
# پاکسازی cache (هر 6 ساعت)
cleanup_old_cache.delay()

# پاکسازی query cache (روزانه)
cleanup_query_cache.delay(days=30)

# آرشیو مکالمات قدیمی
cleanup_old_conversations.delay(days=90)

# پاکسازی taskهای failed
cleanup_failed_tasks.delay()
```

#### User Tasks (4 tasks)
```python
# ریست محدودیت یک کاربر
reset_user_daily_limit.delay(user_id)

# ریست همه کاربران (نیمه‌شب)
reset_all_daily_limits.delay()

# به‌روزرسانی آمار کاربر
update_user_statistics.delay(user_id)

# محاسبه tier کاربر
calculate_user_tier.delay(user_id)
```

### Periodic Tasks (Celery Beat)

| Task | Schedule | توضیحات |
|------|----------|---------|
| `reset_all_daily_limits` | روزانه 00:00 | ریست محدودیت روزانه |
| `cleanup_old_cache` | هر 6 ساعت | پاکسازی cache |
| `cleanup_query_cache` | روزانه 02:00 | پاکسازی query cache |
| `process_sync_queue` | هر 5 دقیقه | پردازش صف sync |
| `send_usage_statistics` | هر ساعت | ارسال آمار |

### مانیتورینگ با Flower

```bash
# دسترسی به Flower UI
http://localhost:5555

# مشاهده:
# - Active tasks
# - Task history
# - Worker status
# - Task statistics
```

---

## یکپارچه‌سازی

### Ingest System

#### هدف
پردازش اسناد، استخراج متن، و تولید embeddings

#### API Endpoints

```python
# دریافت embedding برای query
POST /api/v1/embeddings/query
{
    "text": "متن سوال کاربر"
}

# Response
{
    "embedding": [0.123, 0.456, ...],
    "model": "text-embedding-ada-002"
}
```

#### پیکربندی

```bash
# در .env
INGEST_API_URL=http://ingest-api:8000
INGEST_API_KEY=your-ingest-key
INGEST_DATABASE_URL=postgresql://user:pass@ingest-db:5432/ingest
```

### Users System

#### هدف
مدیریت کاربران، احراز هویت، و اعلان‌ها

#### Integration Points

```python
# ارسال نتیجه query
POST /notifications/webhook
{
    "event_type": "query_completed",
    "user_id": "user-123",
    "data": {
        "conversation_id": "conv-456",
        "query": "سوال",
        "answer": "پاسخ",
        "tokens_used": 150
    }
}

# ارسال آمار
POST /statistics/core
{
    "event_type": "usage_statistics",
    "data": {
        "total_queries": 150,
        "total_tokens": 45000,
        "active_users": 25
    }
}
```

#### پیکربندی

```bash
# در .env
USERS_API_URL=http://users-api:9000
USERS_API_KEY=your-users-key
```

---

## API Reference

### Authentication

همه APIها نیاز به API key دارند:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:7001/api/v1/...
```

### Query Processing

```bash
# پردازش query
POST /api/v1/query/
{
    "query": "سوال کاربر",
    "conversation_id": "optional-uuid",
    "user_id": "user-123"
}

# Response
{
    "answer": "پاسخ سیستم",
    "sources": ["source1", "source2"],
    "conversation_id": "uuid",
    "message_id": "uuid",
    "tokens_used": 150,
    "processing_time_ms": 1200,
    "cached": false
}
```

### User Management

```bash
# ایجاد/دریافت کاربر
POST /api/v1/users/profile
{
    "user_id": "user-123",
    "name": "نام کاربر"
}

# دریافت مکالمات کاربر
GET /api/v1/users/{user_id}/conversations

# دریافت تاریخچه مکالمه
GET /api/v1/users/conversations/{conversation_id}/messages
```

### Sync Management

```bash
# همگام‌سازی embeddings
POST /api/v1/sync/embeddings
{
    "batch_size": 100,
    "since": "2025-11-15T00:00:00Z"
}

# همگام‌سازی کامل (async via Celery)
POST /api/v1/sync/trigger-full-sync

# حذف embeddings یک سند
DELETE /api/v1/sync/document/{document_id}
```

### Task Management

```bash
# وضعیت یک task
GET /api/v1/tasks/status/{task_id}

# لیست taskهای فعال
GET /api/v1/tasks/list

# لغو task
POST /api/v1/tasks/revoke/{task_id}

# آمار workers
GET /api/v1/tasks/workers
```

### Health Check

```bash
# بررسی سلامت سیستم
GET /health

# Response
{
    "status": "healthy",
    "version": "1.0.0",
    "environment": "production",
    "services": {
        "database": "healthy",
        "redis": "healthy",
        "qdrant": "healthy"
    }
}
```

---

## عیب‌یابی

### مشکلات رایج

#### 1. خطای ContainerConfig

**علامت:**
```
KeyError: 'ContainerConfig'
```

**راه‌حل:**
```bash
cd /srv/deployment/docker
docker-compose stop
docker-compose rm -f
docker-compose up -d
```

#### 2. Database Connection Error

**علامت:**
```
password authentication failed for user "core_user"
```

**راه‌حل:**
```bash
# بررسی .env
cat /srv/.env | grep POSTGRES_PASSWORD

# بررسی container
docker-compose exec postgres-core env | grep POSTGRES_PASSWORD

# اگر مختلف بودند، restart کنید
docker-compose restart postgres-core
```

#### 3. Celery Worker نمی‌تواند task پیدا کند

**علامت:**
```
Received unregistered task
```

**راه‌حل:**
```bash
# Rebuild و restart
docker-compose build celery-worker
docker-compose restart celery-worker
```

#### 4. Qdrant Unhealthy

**علامت:**
```
qdrant: Up (unhealthy)
```

**راه‌حل:**
```bash
# معمولاً بعد از چند دقیقه healthy می‌شود
# اگر نشد:
docker-compose restart qdrant
docker-compose logs qdrant
```

### لاگ‌ها

```bash
# همه سرویس‌ها
docker-compose logs -f

# یک سرویس خاص
docker-compose logs -f core-api
docker-compose logs -f celery-worker
docker-compose logs -f postgres-core

# آخرین 100 خط
docker-compose logs --tail=100 core-api
```

### Backup و Restore

```bash
# ایجاد backup
./backup.sh backup

# لیست backupها
./backup.sh list

# Restore
./backup.sh restore /var/lib/core/backups/core_backup_20251115_093000.tar.gz

# پاکسازی backupهای قدیمی
./backup.sh clean
```

### Performance Tuning

#### افزایش Celery Workers

```yaml
# در docker-compose.yml
celery-worker:
  command: celery -A app.celery_app worker --concurrency=8
```

#### افزایش Connection Pool

```bash
# در .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

#### Cache Settings

```bash
# در .env
REDIS_MAX_CONNECTIONS=50
CACHE_TTL=3600
```

---

## منابع و لینک‌های مفید

### مستندات رسمی
- [FastAPI](https://fastapi.tiangolo.com/)
- [Celery](https://docs.celeryq.dev/)
- [Qdrant](https://qdrant.tech/documentation/)
- [Docker](https://docs.docker.com/)

### پشتیبانی
- مستندات: `/srv/document/`
- لاگ‌ها: `docker-compose logs`
- Health check: `http://localhost:7001/health`

---

**آخرین به‌روزرسانی:** 2025-11-15  
**نسخه:** 1.0.0
