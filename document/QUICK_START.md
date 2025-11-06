# 🚀 شروع سریع - Core System

## ✅ تغییرات انجام شده

### قبل از تغییرات:
- ❌ Provider های مختلف (OpenAI, Anthropic, Hugging Face, Local, Persian)
- ❌ تنظیمات پیچیده برای هر provider
- ❌ فایل‌های مجزا برای هر provider

### بعد از تغییرات:
- ✅ **یک** Provider واحد (OpenAI-compatible)
- ✅ تنظیمات ساده (فقط 3 پارامتر اصلی)
- ✅ پشتیبانی از همه API های سازگار با OpenAI

---

## 📝 تنظیم LLM در 3 قدم

### قدم 1: انتخاب Provider

برای **شروع سریع** توصیه می‌کنم: **Groq** (رایگان و سریع)

### قدم 2: ویرایش .env

```bash
cd /home/ahad/project/core
nano .env
```

**برای Groq:**
```bash
LLM_API_KEY="gsk_YourGroqKeyHere"              # API Key خود را بگذارید
LLM_BASE_URL="https://api.groq.com/openai/v1"  # Base URL
LLM_MODEL="llama-3.1-70b-versatile"            # نام مدل
```

**برای OpenAI:**
```bash
LLM_API_KEY="sk-YourOpenAIKeyHere"   # API Key خود را بگذارید
LLM_BASE_URL=""                      # خالی بگذارید
LLM_MODEL="gpt-4-turbo-preview"      # نام مدل
```

### قدم 3: Restart و تست

```bash
# Restart API
pkill -f "uvicorn app.main:app"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload

# تست
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "سلام", "language": "fa"}'
```

---

## 🎯 کجا API Key بگیرم؟

### Groq (توصیه شده - رایگان!)
1. https://console.groq.com
2. Sign up
3. API Keys → Create API Key
4. کپی کنید

### OpenAI
1. https://platform.openai.com
2. API Keys → Create new secret key
3. کپی کنید

### سایر Provider ها
راهنمای کامل: `/home/ahad/project/core/document/LLM_SETUP_GUIDE.md`

---

## 📚 فایل‌های مهم

| فایل | توضیحات |
|------|---------|
| `.env` | تنظیمات اصلی (API Key اینجاست) |
| `document/LLM_SETUP_GUIDE.md` | راهنمای کامل LLM |
| `SYSTEM_STATUS.md` | وضعیت سیستم و دستورات |
| `app/llm/openai_provider.py` | کد اصلی LLM |
| `app/config/settings.py` | تنظیمات سیستم |

---

## 🔧 پارامترهای .env

### پارامترهای اصلی (ضروری):
```bash
LLM_API_KEY=""        # API Key یا Token
LLM_BASE_URL=""       # Base URL (یا خالی برای OpenAI)
LLM_MODEL=""          # نام مدل
```

### پارامترهای اختیاری (یکبار تعریف):
```bash
LLM_MAX_TOKENS=4096   # حداکثر توکن خروجی
LLM_TEMPERATURE=0.7   # درجه خلاقیت (0.0-2.0)
```

### پارامترهای Embedding (برای Ingest):
```bash
EMBEDDING_MODEL="text-embedding-3-large"
EMBEDDING_API_KEY=""   # خالی = استفاده از LLM_API_KEY
EMBEDDING_BASE_URL=""  # خالی = استفاده از LLM_BASE_URL
```

---

## 🧪 تست سریع

### 1. چک وضعیت:
```bash
curl http://localhost:7001/health
```

### 2. تست LLM:
```bash
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون کار ایران چیست؟",
    "language": "fa",
    "max_results": 5
  }'
```

### 3. مرورگر:
```
http://localhost:7001/docs
```

---

## 🎨 Provider های پشتیبانی شده

هر API که با OpenAI سازگار باشد:

✅ **OpenAI** (GPT-4, GPT-3.5)
✅ **Groq** (Llama-3.1, Mixtral)
✅ **Together.ai** (مدل‌های متنوع)
✅ **DeepSeek** (ارزان)
✅ **Mistral AI** (Mistral, Mixtral)
✅ **LM Studio** (Local)
✅ **LocalAI** (Local)
✅ **Ollama** (با Wrapper)

---

## ❓ سوالات متداول

### چگونه Provider را تغییر دهم؟
فقط `LLM_API_KEY` و `LLM_BASE_URL` را در `.env` تغییر دهید و API را restart کنید.

### چگونه مدل را تغییر دهم؟
`LLM_MODEL` را در `.env` تغییر دهید.

### چند Provider می‌توانم داشته باشم؟
فقط **یک** Provider در یک زمان. برای تغییر، `.env` را ویرایش کنید.

### Embedding از کجا می‌آید؟
اگر `EMBEDDING_API_KEY` خالی باشد، از `LLM_API_KEY` استفاده می‌شود.

### چگونه مطمئن شوم کار می‌کند؟
```bash
curl http://localhost:7001/health
```

---

## 🛠 عیب‌یابی

### API بالا نمی‌آید:
```bash
# چک کنید در حال اجراست
ps aux | grep uvicorn

# چک کنید لاگ‌ها
tail -f logs/app.log
```

### خطای API Key:
```bash
# مطمئن شوید فضای خالی ندارد
grep LLM_API_KEY .env

# مطمئن شوید به درستی set شده
echo $LLM_API_KEY
```

### خطای Connection:
```bash
# BASE_URL را چک کنید
grep LLM_BASE_URL .env

# مثلاً برای Groq باید باشد:
# LLM_BASE_URL="https://api.groq.com/openai/v1"
```

---

## 📞 راهنما و پشتیبانی

- **راهنمای کامل LLM**: `document/LLM_SETUP_GUIDE.md`
- **وضعیت سیستم**: `SYSTEM_STATUS.md`
- **API Docs**: http://localhost:7001/docs

---

## ✨ مثال کامل (Groq)

```bash
# 1. ویرایش .env
nano .env

# 2. این خطوط را پیدا و تغییر دهید:
LLM_API_KEY="gsk_abc123..."
LLM_BASE_URL="https://api.groq.com/openai/v1"
LLM_MODEL="llama-3.1-70b-versatile"

# 3. Restart
pkill -f uvicorn
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload

# 4. تست
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query":"سلام","language":"fa"}'
```

---

**🎉 آماده‌اید! سیستم ساده شد و حالا راحت‌تر است!**
