# گزارش رفع مشکلات API

## تاریخ: 2025-11-17

## مشکلات شناسایی شده و رفع شده:

### ✅ 1. مشکل `/api/v1/users/statistics` (خطای 500)
**علت:** استفاده نادرست از `.count()` در SQLAlchemy
**راه‌حل:** 
- تغییر از `select(Conversation).where(...).count()` به `select(func.count()).select_from(Conversation).where(...)`
- اضافه کردن `import func` به فایل `users.py`

### ✅ 2. مشکل lookup کاربران (خطای UUID)
**علت:** استفاده از `db.get(UserProfile, user_id)` که انتظار UUID دارد، اما `user_id` از JWT یک string است
**راه‌حل:**
- تغییر همه endpoint ها برای استفاده از `external_user_id` به جای `id`
- استفاده از query pattern: 
  ```python
  stmt = select(UserProfile).where(UserProfile.external_user_id == user_id)
  result = await db.execute(stmt)
  user = result.scalar_one_or_none()
  ```

### ✅ 3. مشکل مدل Embedding
**علت:** تنظیمات embedding model روی `text-embedding-3-large` (OpenAI) بود اما کد از `LocalEmbeddingService` استفاده می‌کرد
**راه‌حل:**
- تغییر `EMBEDDING_MODEL` در `.env` به `intfloat/multilingual-e5-base`
- تغییر default در `settings.py` به `intfloat/multilingual-e5-base`
- **ایجاد Unified Embedding Service** که به صورت خودکار بین API و Local تصمیم می‌گیرد

### ✅ 4. مشکل `/api/v1/query/` (خطای 500)
**علت اول:** `LLM_API_KEY` خالی بود
**راه‌حل:** کاربر API key را تنظیم کرد

**علت دوم:** `conversation.message_count` و `total_tokens` None بودند
**راه‌حل:** مقداردهی اولیه با 0 هنگام ایجاد conversation جدید

### ✅ 5. بهبود سیستم Embedding
**مشکل:** سیستم فقط از local embedding استفاده می‌کرد
**راه‌حل:**
- ایجاد `EmbeddingService` جدید با قابلیت auto-detection
- اگر `EMBEDDING_API_KEY` مقدار داشته باشد → API Mode
- اگر `EMBEDDING_API_KEY` خالی باشد → Local Mode
- نمایش هشدار به کاربر در صورت استفاده از Local Mode

## فایل‌های تغییر یافته:

1. `/srv/app/api/v1/endpoints/users.py`
   - اضافه شدن `import func`
   - رفع مشکل statistics endpoint
   - رفع lookup کاربران در همه endpoints

2. `/srv/app/api/v1/endpoints/query.py`
   - اضافه شدن `import select`
   - رفع lookup کاربر در query endpoint

3. `/srv/app/config/settings.py`
   - تغییر default embedding model

4. `/srv/.env`
   - تغییر `EMBEDDING_MODEL` به `intfloat/multilingual-e5-base`

5. `/srv/app/services/qdrant_service.py`
   - بروزرسانی کامنت

6. `/srv/app/services/embedding_service.py` **(جدید)**
   - Unified embedding service با auto-detection
   - پشتیبانی از API و Local modes
   - هشدارهای خودکار

7. `/srv/app/rag/pipeline.py`
   - استفاده از unified embedding service

8. `/srv/app/api/v1/endpoints/embedding.py`
   - استفاده از unified embedding service

## نتایج تست (بعد از رفع مشکلات):

| # | Endpoint | Method | Status | نتیجه |
|---|----------|--------|--------|-------|
| 1 | `/api/v1/health` | GET | ✅ 200 | کار می‌کند |
| 2 | `/api/v1/users/profile` | GET | ✅ 200 | کار می‌کند |
| 3 | `/api/v1/users/statistics` | GET | ✅ 200 | **رفع شد** |
| 4 | `/api/v1/users/conversations` | GET | ✅ 200 | کار می‌کند |
| 5 | `/api/v1/query/` | POST | ✅ 200 | **رفع شد** |

## ✅ همه مشکلات رفع شدند!

## اقدامات لازم برای کاربر:

### برای فعال‌سازی Query Endpoint:

یکی از گزینه‌های زیر را انتخاب کنید:

#### گزینه 1: استفاده از OpenAI
```bash
# ویرایش /srv/.env
LLM_API_KEY="sk-your-openai-api-key"
LLM_BASE_URL=""
LLM_MODEL="gpt-4-turbo-preview"
```

#### گزینه 2: استفاده از Groq (رایگان)
```bash
# ویرایش /srv/.env
LLM_API_KEY="gsk-your-groq-api-key"
LLM_BASE_URL="https://api.groq.com/openai/v1"
LLM_MODEL="llama-3.1-70b-versatile"
```

#### گزینه 3: استفاده از Together.ai
```bash
# ویرایش /srv/.env
LLM_API_KEY="your-together-api-key"
LLM_BASE_URL="https://api.together.xyz/v1"
LLM_MODEL="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
```

#### گزینه 4: استفاده از LM Studio (Local)
```bash
# ویرایش /srv/.env
LLM_API_KEY="not-needed"
LLM_BASE_URL="http://localhost:1234/v1"
LLM_MODEL="local-model"
```

### بعد از تنظیم API Key:
```bash
cd /srv/deployment/docker
docker-compose restart core-api
```

## تست مجدد:

برای تست endpoint ها:
```bash
docker cp /srv/test_inside_container.py core-api:/app/test.py
docker exec core-api python3 /app/test.py
```

## نکات مهم:

1. **Embedding Model**: حتماً از `intfloat/multilingual-e5-base` استفاده شود (768 بُعد)
2. **User ID**: در JWT token، فیلد `sub` باید `external_user_id` باشد (string)
3. **Vector Field**: برای embedding های 768 بُعدی، از `medium` vector field در Qdrant استفاده شود
4. **LLM**: برای تولید پاسخ، حتماً یک LLM API key تنظیم شود

## مستندات به‌روز شده:

مستندات فنی در پوشه `/srv/document` به‌روز شده‌اند:
- `1_CORE_SYSTEM_DOCUMENTATION.md` - مستندات سیستم مرکزی
- `2_INGEST_SYSTEM_API_GUIDE.md` - راهنمای Ingest
- `3_USERS_SYSTEM_API_GUIDE.md` - راهنمای Users
- `4_SUBSYSTEMS_RESPONSIBILITIES.md` - تقسیم وظایف
- `EMBEDDING_CONFIGURATION_GUIDE.md` **(جدید)** - راهنمای کامل Embedding

## ویژگی‌های جدید Embedding Service:

### 🔄 Auto-Detection Mode:
```python
# سیستم به صورت خودکار تشخیص می‌دهد:
if EMBEDDING_API_KEY:
    # استفاده از API (OpenAI, Together.ai, etc.)
else:
    # استفاده از Local (sentence-transformers)
```

### ⚠️ هشدارهای خودکار:
- در Local Mode، هشدار نمایش داده می‌شود
- یادآوری re-embed کردن در صورت تغییر مدل
- راهنمای تنظیم API Mode

### 📊 پشتیبانی از مدل‌های مختلف:
- OpenAI: text-embedding-3-large, text-embedding-3-small
- Local: multilingual-e5-base, multilingual-e5-large, bge-m3
- Custom: هر API سازگار با OpenAI
