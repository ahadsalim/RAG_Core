# ✅ Core System - آماده و در حال اجرا!

تاریخ: 2025-11-01
وضعیت: **RUNNING** 🚀

---

## 🎯 وضعیت سرویس‌ها

### ✅ سرویس‌های در حال اجرا

| سرویس | پورت | وضعیت | آدرس |
|-------|------|-------|------|
| **Core API** | 7001 | ✅ Running | http://localhost:7001 |
| **PostgreSQL** | 7433 | ✅ Healthy | localhost:7433 |
| **Redis** | 7379 | ✅ Healthy | localhost:7379 |
| **Qdrant** | 7333 | ✅ Running | http://localhost:7333 |
| **Prometheus** | - | ✅ Enabled | http://localhost:7001/metrics |

---

## 🔍 چگونه بفهمیم سیستم کار می‌کند؟

### روش 1: مرورگر (ساده‌ترین)

```bash
# باز کردن API Docs
firefox http://localhost:7001/docs

# یا
google-chrome http://localhost:7001/docs
```

### روش 2: Terminal

```bash
# چک سلامت کلی
curl http://localhost:7001/health

# اطلاعات سیستم
curl http://localhost:7001/

# مستندات API
curl http://localhost:7001/openapi.json
```

### روش 3: Python

```python
import requests

# تست پایه
response = requests.get("http://localhost:7001/")
print(response.json())
# Output: {'name': 'RAG Core System', 'version': '1.0.0', ...}

# چک سلامت
health = requests.get("http://localhost:7001/health")
print(health.json())
```

---

## 🧪 تست Llama-3.1 (Hugging Face)

### قبل از تست:

توکن Hugging Face را در `.env` بگذارید:
```bash
cd /home/ahad/project/core
nano .env

# این خط را پیدا کنید و توکن بگذارید:
HUGGINGFACE_API_KEY="hf_xxxxxxxxxxxxx"
ACTIVE_LLM_PROVIDER="huggingface"
```

### تست با curl:

```bash
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون کار ایران چیست؟",
    "language": "fa"
  }'
```

### تست با Python:

```python
import requests

response = requests.post(
    "http://localhost:7001/api/v1/query",
    json={
        "query": "قانون کار ایران چیست؟",
        "language": "fa"
    }
)

print(response.json())
```

---

## 📍 لینک‌های مهم

### API Endpoints
- **Root**: http://localhost:7001/
- **Docs (Swagger)**: http://localhost:7001/docs
- **ReDoc**: http://localhost:7001/redoc
- **OpenAPI Schema**: http://localhost:7001/openapi.json
- **Health Check**: http://localhost:7001/health
- **Metrics**: http://localhost:7001/metrics

### Admin Endpoints
- **Users**: http://localhost:7001/api/v1/admin/users
- **Stats**: http://localhost:7001/api/v1/admin/stats
- **Cache**: http://localhost:7001/api/v1/admin/cache

### Query Endpoints
- **Query**: POST http://localhost:7001/api/v1/query
- **Stream**: POST http://localhost:7001/api/v1/query/stream
- **History**: GET http://localhost:7001/api/v1/history

---

## 🎨 مشاهده Swagger UI

1. **باز کردن مرورگر**:
   ```bash
   firefox http://localhost:7001/docs
   ```

2. **تست endpoint ها**:
   - روی هر endpoint کلیک کنید
   - "Try it out" بزنید
   - پارامترها را پر کنید
   - "Execute" بزنید

3. **Authentication** (اگر لازم باشد):
   - روی 🔒 کلیک کنید
   - Token را وارد کنید

---

## 📊 مانیتورینگ

### چک لاگ‌ها:

```bash
# لاگ‌های API
tail -f /home/ahad/project/core/logs/app.log

# لاگ‌های Docker
docker logs -f postgres-core
docker logs -f redis-core
docker logs -f qdrant
```

### چک Metrics:

```bash
curl http://localhost:7001/metrics
```

---

## 🛑 توقف سیستم

```bash
# توقف API
pkill -f "uvicorn app.main:app"

# توقف Docker services
cd /home/ahad/project/core/deployment
docker-compose -f docker/docker-compose.yml down
```

---

## 🚀 شروع مجدد

```bash
cd /home/ahad/project/core

# شروع services
cd deployment
docker-compose -f docker/docker-compose.yml up -d postgres-core redis-core qdrant

# شروع API
cd ..
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

---

## ⚙️ تنظیمات فعلی

### LLM Provider
```
Active Provider: Hugging Face
Model: meta-llama/Llama-3.1-8B-Instruct
```

### Ports
```
API: 7001
PostgreSQL: 7433
Redis: 7379
Qdrant: 7333/7334
```

### Environment
```
Mode: Development
Debug: True
Reload: True
```

---

## 📚 مستندات

- **راهنمای Llama**: `/home/ahad/project/core/document/HUGGINGFACE_LLAMA_SETUP.md`
- **Setup کامل**: `/home/ahad/project/core/SETUP_COMPLETE.md`
- **API Keys**: `/home/ahad/project/core/document/API_KEYS_SETUP.md`

---

## ❓ عیب‌یابی

### API پاسخ نمی‌دهد؟
```bash
# چک کنید که process در حال اجرا است
ps aux | grep uvicorn

# اگر نیست، دوباره شروع کنید
cd /home/ahad/project/core
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

### خطای Database?
```bash
# Restart PostgreSQL
docker restart postgres-core
```

### خطای Qdrant?
```bash
# Restart Qdrant
docker restart qdrant
```

---

## ✨ تست نهایی

برای اطمینان از اینکه همه چیز کار می‌کند:

```bash
# تست 1: Root endpoint
curl http://localhost:7001/

# تست 2: Health check
curl http://localhost:7001/health

# تست 3: Docs
curl -I http://localhost:7001/docs

# تست 4: Services
docker ps | grep -E "(postgres-core|redis-core|qdrant)"
```

اگر همه این تست‌ها موفق بودند، سیستم آماده است! 🎉
