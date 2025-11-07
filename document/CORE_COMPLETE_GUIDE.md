# 📚 راهنمای جامع سیستم Core

**نسخه:** 2.0  
**تاریخ:** 2024-11-06  
**وضعیت:** Production Ready

---

# فهرست مطالب

1. [معرفی سیستم](#معرفی-سیستم)
2. [معماری و فناوری‌ها](#معماری-و-فناوریها)
3. [راه‌اندازی سریع](#راهاندازی-سریع)
4. [API Documentation](#api-documentation)
5. [یکپارچه‌سازی با Ingest](#یکپارچهسازی-با-ingest)
6. [عملیات CRUD روی نودها](#عملیات-crud-روی-نودها)
7. [تنظیمات LLM](#تنظیمات-llm)
8. [تنظیمات Embedding](#تنظیمات-embedding)
9. [مدیریت کاربران](#مدیریت-کاربران)
10. [نکات بهینه‌سازی](#نکات-بهینهسازی)

---

# معرفی سیستم

## 🎯 هدف
سیستم Core مغز متفکر و موتور پردازشی پروژه RAG است که مسئول:
- پردازش سوالات کاربران
- جستجوی معنایی در اسناد حقوقی
- تولید پاسخ‌های هوشمند با استفاده از LLM
- مدیریت embeddings و vector database
- همگام‌سازی با سیستم Ingest

## ✨ ویژگی‌های کلیدی
- ✅ جستجوی معنایی پیشرفته (Semantic Search)
- ✅ پشتیبانی از چند LLM (GPT, Claude, Llama, مدل‌های ایرانی)
- ✅ RAG Pipeline کامل
- ✅ Multi-layer Caching
- ✅ API کامل برای Ingest
- ✅ مدیریت کاربران و احراز هویت
- ✅ Swagger UI برای تست API

---

# معماری و فناوری‌ها

## 🏗️ Stack فناوری

### Backend
- **FastAPI** - فریمورک وب سریع و مدرن
- **Python 3.11+** - زبان برنامه‌نویسی
- **Pydantic** - اعتبارسنجی داده‌ها

### Databases
- **Qdrant** - پایگاه داده برداری (Vector DB)
- **PostgreSQL 15+** - پایگاه داده رابطه‌ای
- **Redis 7+** - کش و صف پیام

### AI/ML
- **LangChain** - مدیریت LLM و RAG
- **Sentence Transformers** - تولید embeddings
- **OpenAI / Anthropic / Local LLMs** - مدل‌های زبانی

### Infrastructure
- **Docker & Docker Compose** - کانتینریزه‌سازی
- **Nginx** - Reverse proxy
- **Celery** - پردازش ناهمزمان

## 📊 معماری سیستم

```
┌─────────────┐
│   Ingest    │ ──────► Embeddings + Metadata
└─────────────┘              │
                             ▼
                    ┌─────────────────┐
                    │   Core API      │
                    │   (FastAPI)     │
                    └─────────────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
         ┌──────────┐  ┌─────────┐  ┌────────┐
         │  Qdrant  │  │  Redis  │  │  LLM   │
         │ (Vectors)│  │ (Cache) │  │(GPT/...)│
         └──────────┘  └─────────┘  └────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │  (Users, Logs)  │
                    └─────────────────┘
```

---

# راه‌اندازی سریع

## 🚀 نصب با Docker (توصیه می‌شود)

### 1. Clone و Setup:
```bash
cd /srv
git clone <repository>
cd core
```

### 2. تنظیم Environment:
```bash
cp .env.example .env
nano .env
```

**متغیرهای مهم:**
```env
# API Settings
APP_NAME="Core RAG System"
DEBUG=false
API_HOST=0.0.0.0
API_PORT=7001

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/core_db

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=legal_documents

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# LLM (OpenAI example)
OPENAI_API_KEY=sk-...
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4

# Embedding
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768

# API Keys
INGEST_API_KEY=hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/
JWT_SECRET_KEY=<generate-random-key>
```

### 3. راه‌اندازی:
```bash
cd deployment/docker
docker-compose up -d
```

### 4. بررسی:
```bash
# Health check
curl http://localhost:7001/health

# Swagger UI
open http://localhost:7001/docs
```

## 🔧 نصب محلی (Development)

```bash
# Virtual environment
python -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Database migration
alembic upgrade head

# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 7001
```

---

# API Documentation

## 📍 Base URL
- **Development:** `http://localhost:7001`
- **Production:** `https://core.arpanet.ir`

## 🔐 Authentication

### برای Ingest (API Key):
```http
X-API-Key: hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/
```

### برای کاربران (JWT):
```http
Authorization: Bearer <jwt_token>
```

## 📚 Endpoints اصلی

### 1. Health & Status
```http
GET /health
GET /ready
GET /report
```

### 2. Sync API (برای Ingest)

#### ارسال Embeddings:
```http
POST /api/v1/sync/embeddings
Content-Type: application/json
X-API-Key: ...

{
  "embeddings": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "vector": [0.123, -0.456, ...],
      "text": "ماده ۱ - این قانون...",
      "document_id": "law-123",
      "document_type": "LAW",
      "chunk_index": 0,
      "language": "fa",
      "source": "ingest",
      "metadata": {
        "work_title": "قانون...",
        "authority": "مجلس...",
        "approval_date": "1400/01/01"
      }
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "synced_count": 1,
  "node_ids": ["550e8400-..."],
  "timestamp": "2024-11-06T15:00:00"
}
```

#### دریافت اطلاعات نود:
```http
GET /api/v1/sync/node/{node_id}
X-API-Key: ...
```

**Response:**
```json
{
  "node_id": "550e8400-...",
  "exists": true,
  "vector": [0.123, ...],
  "text": "ماده ۱ - ...",
  "document_id": "law-123",
  "document_type": "LAW",
  "chunk_index": 0,
  "language": "fa",
  "source": "ingest",
  "metadata": {...},
  "created_at": "2024-11-06T10:00:00",
  "updated_at": null,
  "vector_dimensions": {"medium": 768}
}
```

#### به‌روزرسانی نود:
```http
PUT /api/v1/sync/node/{node_id}
X-API-Key: ...

{
  "id": "550e8400-...",
  "vector": [0.789, ...],
  "text": "متن جدید",
  "document_id": "law-123",
  "document_type": "LAW",
  "metadata": {...}
}
```

#### حذف نود:
```http
DELETE /api/v1/sync/node/{node_id}
X-API-Key: ...
```

#### آمار سیستم:
```http
GET /api/v1/sync/statistics
X-API-Key: ...
```

**Response:**
```json
{
  "timestamp": "2024-11-06T15:00:00",
  "postgresql": {
    "users": {"total": 150},
    "conversations": {"total": 500},
    "messages": {"total": 2000}
  },
  "qdrant": {
    "collection_name": "legal_documents",
    "points_count": 10000,
    "vectors_count": 10000,
    "status": "green"
  },
  "summary": {
    "total_users": 150,
    "total_vectors": 10000
  }
}
```

### 3. Query API (برای کاربران)

```http
POST /api/v1/query
Authorization: Bearer <jwt_token>

{
  "query": "قانون حمایت از مصرف‌کننده چیست؟",
  "conversation_id": "conv-123",
  "filters": {
    "document_type": "LAW",
    "jurisdiction": "IR"
  }
}
```

### 4. Admin API

```http
GET /api/v1/admin/stats
GET /api/v1/admin/cache/stats
POST /api/v1/admin/cache/clear
```

---

# یکپارچه‌سازی با Ingest

## 🔄 Workflow کامل

### 1. Ingest تولید node_id می‌کند:
```python
import uuid

node_id = str(uuid.uuid4())
```

### 2. Ingest embedding تولید می‌کند:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('intfloat/multilingual-e5-base')
vector = model.encode(text).tolist()
```

### 3. Ingest به Core ارسال می‌کند:
```python
import requests

response = requests.post(
    "https://core.arpanet.ir/api/v1/sync/embeddings",
    json={
        "embeddings": [{
            "id": node_id,
            "vector": vector,
            "text": text,
            "document_id": doc_id,
            "document_type": "LAW",
            "chunk_index": 0,
            "language": "fa",
            "source": "ingest",
            "metadata": {...}
        }]
    },
    headers={
        "X-API-Key": "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
    }
)

result = response.json()
node_ids = result['node_ids']  # لیست node_id های ارسال شده
```

### 4. Ingest node_id را ذخیره می‌کند:
```python
db.execute("""
    UPDATE legalunit
    SET node_id = %s, synced_at = NOW()
    WHERE id = %s
""", (node_id, legalunit_id))
```

### 5. Ingest می‌تواند تایید کند:
```python
response = requests.get(
    f"https://core.arpanet.ir/api/v1/sync/node/{node_id}",
    headers={"X-API-Key": "..."}
)

node_data = response.json()
if node_data['exists'] and node_data['text'] == original_text:
    print("✅ داده صحیح ذخیره شده")
```

## 🔑 نکات مهم

### 1. Idempotency:
- اگر با همان `node_id` دوباره ارسال شود، update می‌شود (upsert)
- نگران duplicate نباشید

### 2. Batch Processing:
- می‌توانید تا 100 embedding در یک request ارسال کنید
- برای تعداد بیشتر، batch کنید

### 3. Error Handling:
```python
try:
    response = requests.post(...)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("❌ API Key نامعتبر")
    elif e.response.status_code == 400:
        print("❌ داده نامعتبر")
    else:
        print(f"❌ خطا: {e}")
```

### 4. Retry Logic:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def send_to_core(data):
    response = requests.post(...)
    response.raise_for_status()
    return response.json()
```

---

# عملیات CRUD روی نودها

## ✅ Create (ایجاد)
```python
POST /api/v1/sync/embeddings
```

## 📖 Read (خواندن)
```python
GET /api/v1/sync/node/{node_id}
```

## 🔄 Update (به‌روزرسانی)
```python
PUT /api/v1/sync/node/{node_id}
```

## ❌ Delete (حذف)
```python
DELETE /api/v1/sync/node/{node_id}
```

## 💻 کلاس کامل برای Ingest:

```python
import requests
from typing import Dict, Any, List

class CoreNodeManager:
    """مدیریت عملیات CRUD روی نودهای Core"""
    
    def __init__(self):
        self.base_url = "https://core.arpanet.ir/api/v1/sync"
        self.api_key = "hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/"
        self.headers = {"X-API-Key": self.api_key}
    
    def create_node(self, node_id: str, vector: List[float], 
                   text: str, document_id: str, **kwargs) -> Dict:
        """ایجاد نود جدید"""
        response = requests.post(
            f"{self.base_url}/embeddings",
            json={"embeddings": [{
                "id": node_id,
                "vector": vector,
                "text": text,
                "document_id": document_id,
                **kwargs
            }]},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def read_node(self, node_id: str) -> Dict:
        """خواندن اطلاعات نود"""
        response = requests.get(
            f"{self.base_url}/node/{node_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def update_node(self, node_id: str, vector: List[float],
                   text: str, document_id: str, **kwargs) -> Dict:
        """به‌روزرسانی نود"""
        response = requests.put(
            f"{self.base_url}/node/{node_id}",
            json={
                "id": node_id,
                "vector": vector,
                "text": text,
                "document_id": document_id,
                **kwargs
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def delete_node(self, node_id: str) -> Dict:
        """حذف نود"""
        response = requests.delete(
            f"{self.base_url}/node/{node_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def node_exists(self, node_id: str) -> bool:
        """بررسی وجود نود"""
        try:
            result = self.read_node(node_id)
            return result.get('exists', False)
        except:
            return False
```

---

# تنظیمات LLM

## 🤖 مدل‌های پشتیبانی شده

### 1. OpenAI (GPT)
```env
OPENAI_API_KEY=sk-...
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4
```

### 2. Anthropic (Claude)
```env
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-3-opus-20240229
```

### 3. Local LLM (Llama)
```env
LLM_API_BASE=http://localhost:8000/v1
DEFAULT_LLM_PROVIDER=local
DEFAULT_LLM_MODEL=llama-3-8b-instruct
```

### 4. مدل‌های ایرانی
```env
PERSIAN_LLM_API_KEY=...
DEFAULT_LLM_PROVIDER=persian
DEFAULT_LLM_MODEL=persian-llm-v1
```

## ⚙️ تنظیمات پیشرفته

```env
# Temperature (0.0 - 1.0)
LLM_TEMPERATURE=0.7

# Max tokens
LLM_MAX_TOKENS=2000

# Top-p sampling
LLM_TOP_P=0.9

# Streaming
LLM_STREAMING=true
```

---

# تنظیمات Embedding

## 🎯 مدل Embedding

### مدل پیش‌فرض (توصیه می‌شود):
```env
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
```

### مدل‌های دیگر:
```env
# Persian-specific
EMBEDDING_MODEL=HooshvareLab/bert-fa-base-uncased
EMBEDDING_DIMENSION=768

# Multilingual large
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
EMBEDDING_DIMENSION=768
```

## 🚀 بهینه‌سازی

### استفاده از GPU:
```python
# در docker-compose.yml
services:
  core-api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Batch Processing:
```env
EMBEDDING_BATCH_SIZE=32
EMBEDDING_MAX_LENGTH=512
```

---

# مدیریت کاربران

## 👤 سیستم احراز هویت

### ثبت‌نام:
```http
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "نام کاربر"
}
```

### ورود:
```http
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### استفاده از Token:
```http
GET /api/v1/users/profile
Authorization: Bearer eyJ...
```

## 🎫 Subscription Tiers

```python
TIERS = {
    "free": {
        "queries_per_day": 10,
        "max_tokens": 500
    },
    "basic": {
        "queries_per_day": 100,
        "max_tokens": 2000
    },
    "premium": {
        "queries_per_day": 1000,
        "max_tokens": 4000
    },
    "enterprise": {
        "queries_per_day": -1,  # unlimited
        "max_tokens": 8000
    }
}
```

---

# نکات بهینه‌سازی

## ⚡ Performance

### 1. Caching:
```env
# Redis cache
REDIS_CACHE_TTL=3600
QUERY_CACHE_ENABLED=true

# In-memory cache
MEMORY_CACHE_SIZE=1000
```

### 2. Connection Pooling:
```env
# PostgreSQL
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Qdrant
QDRANT_TIMEOUT=30
QDRANT_GRPC_PORT=6334
```

### 3. Async Processing:
```env
# Celery workers
CELERY_WORKERS=4
CELERY_MAX_TASKS_PER_CHILD=1000
```

## 🔍 Qdrant Optimization

### Index Settings:
```python
# در qdrant_service.py
collection_config = {
    "vectors": {
        "medium": {
            "size": 768,
            "distance": "Cosine",
            "hnsw_config": {
                "m": 16,
                "ef_construct": 100
            }
        }
    },
    "optimizers_config": {
        "indexing_threshold": 20000
    }
}
```

### Search Optimization:
```python
search_params = {
    "hnsw_ef": 128,  # بالاتر = دقیق‌تر ولی کندتر
    "exact": False    # True برای دقت کامل
}
```

## 📊 Monitoring

### Health Checks:
```bash
# Basic health
curl http://localhost:7001/health

# Detailed health
curl http://localhost:7001/api/v1/admin/health/detailed \
  -H "X-Admin-Key: ..."
```

### Metrics:
```bash
# System stats
curl http://localhost:7001/api/v1/admin/stats \
  -H "X-Admin-Key: ..."

# Qdrant stats
curl http://localhost:7001/report
```

### Logs:
```bash
# Docker logs
docker logs -f core-api

# Application logs
tail -f /var/log/core/app.log
```

---

# Troubleshooting

## ❌ مشکلات رایج

### 1. Qdrant Connection Error
```bash
# بررسی Qdrant
docker ps | grep qdrant
curl http://localhost:7333/collections

# راه‌حل
docker-compose restart qdrant
```

### 2. Out of Memory
```bash
# افزایش memory در docker-compose.yml
services:
  core-api:
    mem_limit: 4g
    memswap_limit: 4g
```

### 3. Slow Queries
```bash
# بررسی cache
redis-cli INFO stats

# پاک کردن cache
curl -X POST http://localhost:7001/api/v1/admin/cache/clear \
  -H "X-Admin-Key: ..."
```

### 4. API Key Invalid
```bash
# بررسی .env
grep INGEST_API_KEY .env

# تست API key
curl http://localhost:7001/api/v1/sync/statistics \
  -H "X-API-Key: ..."
```

---

# پیوست‌ها

## 📝 Environment Variables کامل

```env
# Application
APP_NAME=Core RAG System
APP_VERSION=2.0.0
DEBUG=false
API_HOST=0.0.0.0
API_PORT=7001

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/core_db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_API_KEY=
QDRANT_COLLECTION=legal_documents
QDRANT_TIMEOUT=30

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_CACHE_TTL=3600

# LLM
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_STREAMING=true

# Embedding
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
EMBEDDING_BATCH_SIZE=32
EMBEDDING_DEVICE=cuda

# Security
JWT_SECRET_KEY=<generate-random-key>
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600
INGEST_API_KEY=hgR19fSBYfIx3D8QvqeYJWLOMR1lAsmEYhwR8aMS6aLLuledhyiKQfS9OqX41PI/

# Features
QUERY_CACHE_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
CELERY_WORKERS=4
```

## 🔗 لینک‌های مفید

- **Swagger UI:** http://localhost:7001/docs
- **ReDoc:** http://localhost:7001/redoc
- **Health Check:** http://localhost:7001/health
- **Qdrant Dashboard:** http://localhost:7333/dashboard

---

**آخرین به‌روزرسانی:** 2024-11-06  
**نگهداری:** Core Development Team
