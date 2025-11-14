# راهنمای تنظیم LLM - ساده و گام به گام

## 🎯 مفهوم اصلی

سیستم Core از **یک** Provider استفاده می‌کند که با هر API سازگار با OpenAI کار می‌کند.

---

## 📝 تنظیمات در فایل .env

فقط **3 پارامتر اصلی** نیاز دارید:

```bash
LLM_API_KEY="your-api-key-here"
LLM_BASE_URL="https://api.example.com/v1"  # یا خالی برای OpenAI
LLM_MODEL="model-name"
```

### پارامترهای اختیاری:
```bash
LLM_MAX_TOKENS=4096        # حداکثر توکن خروجی (برای همه مدل‌ها)
LLM_TEMPERATURE=0.7        # درجه خلاقیت (برای همه مدل‌ها)
```

---

## 🌐 Provider های مختلف

### 1️⃣ **OpenAI** (پیش‌فرض)

```bash
LLM_API_KEY="sk-proj-abc123..."
LLM_BASE_URL=""                    # خالی بگذارید
LLM_MODEL="gpt-4-turbo-preview"
```

**دریافت API Key:**
1. https://platform.openai.com
2. API Keys → Create new secret key

**مدل‌های پیشنهادی:**
- `gpt-4-turbo-preview` - قدرتمند‌ترین
- `gpt-4` - متعادل
- `gpt-3.5-turbo` - سریع و ارزان

---

### 2️⃣ **Groq** (سریع و رایگان!)

```bash
LLM_API_KEY="gsk_abc123..."
LLM_BASE_URL="https://api.groq.com/openai/v1"
LLM_MODEL="llama-3.1-70b-versatile"
```

**دریافت API Key:**
1. https://console.groq.com
2. API Keys → Create API Key

**مدل‌های پیشنهادی:**
- `llama-3.1-70b-versatile` - قدرتمند
- `llama-3.1-8b-instant` - سریع
- `mixtral-8x7b-32768` - context طولانی

**مزایا:**
- ✅ رایگان با محدودیت معقول
- ✅ بسیار سریع (inference)
- ✅ مدل‌های قدرتمند

---

### 3️⃣ **Together.ai**

```bash
LLM_API_KEY="your-together-key"
LLM_BASE_URL="https://api.together.xyz/v1"
LLM_MODEL="meta-llama/Llama-3-70b-chat-hf"
```

**دریافت API Key:**
1. https://api.together.xyz
2. Sign up → Settings → API Keys

**مدل‌های پیشنهادی:**
- `meta-llama/Llama-3-70b-chat-hf`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`
- `Qwen/Qwen2-72B-Instruct`

---

### 4️⃣ **DeepSeek** (ارزان!)

```bash
LLM_API_KEY="sk-..."
LLM_BASE_URL="https://api.deepseek.com/v1"
LLM_MODEL="deepseek-chat"
```

**دریافت API Key:**
1. https://platform.deepseek.com
2. API Keys → Create new key

**مزایا:**
- ✅ بسیار ارزان
- ✅ کیفیت خوب
- ✅ پشتیبانی فارسی

---

### 5️⃣ **Mistral AI**

```bash
LLM_API_KEY="..."
LLM_BASE_URL="https://api.mistral.ai/v1"
LLM_MODEL="mistral-large-latest"
```

**دریافت API Key:**
1. https://console.mistral.ai
2. API keys → Create new key

---

### 6️⃣ **Local (LM Studio, LocalAI)**

```bash
LLM_API_KEY="not-needed"
LLM_BASE_URL="http://localhost:1234/v1"
LLM_MODEL="model-name"
```

**نصب LM Studio:**
1. https://lmstudio.ai را دانلود کنید
2. یک مدل دانلود کنید
3. Local Server را شروع کنید

**مزایا:**
- ✅ رایگان و آفلاین
- ✅ بدون نیاز به API Key
- ✅ حفظ حریم خصوصی

---

## 📊 Embedding Configuration

برای پروژه Ingest که نیاز به embedding دارد:

### اگر با LLM یکسان است:
```bash
EMBEDDING_MODEL="text-embedding-3-large"
EMBEDDING_API_KEY=""        # خالی = استفاده از LLM_API_KEY
EMBEDDING_BASE_URL=""       # خالی = استفاده از LLM_BASE_URL
```

### اگر متفاوت است:
```bash
EMBEDDING_MODEL="text-embedding-3-large"
EMBEDDING_API_KEY="sk-different-key"
EMBEDDING_BASE_URL="https://different-api.com/v1"
```

### مدل‌های Embedding پیشنهادی:

**OpenAI:**
- `text-embedding-3-large` (3072 dim)
- `text-embedding-3-small` (1536 dim)
- `text-embedding-ada-002` (1536 dim)

**Local:**
- `nomic-embed-text` (با Ollama)
- `all-MiniLM-L6-v2` (با LM Studio)

---

## 🧪 تست تنظیمات

### قدم 1: ویرایش .env
```bash
cd /home/ahad/project/core
nano .env
```

### قدم 2: Restart API
```bash
pkill -f "uvicorn app.main:app"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

### قدم 3: تست
```bash
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "سلام، چطوری؟",
    "language": "fa"
  }'
```

---

## 🔍 عیب‌یابی

### خطا: "Invalid API Key"
```bash
# چک کنید API Key صحیح است
echo $LLM_API_KEY

# مطمئن شوید فضای خالی اضافی ندارد
```

### خطا: "Connection Error"
```bash
# چک کنید BASE_URL صحیح است
# مثلاً برای Groq:
LLM_BASE_URL="https://api.groq.com/openai/v1"
```

### خطا: "Model not found"
```bash
# لیست مدل‌های موجود را چک کنید:
# OpenAI: https://platform.openai.com/docs/models
# Groq: https://console.groq.com/docs/models
```

### چک لاگ‌ها:
```bash
# در ترمینالی که API را اجرا کردید لاگ‌ها را ببینید
# یا:
tail -f /home/ahad/project/core/logs/app.log
```

---

## 💡 توصیه‌ها

### برای تست و توسعه:
✅ **Groq** - رایگان و سریع

### برای پروداکشن (فارسی عالی):
✅ **OpenAI GPT-4** - کیفیت بالا
✅ **DeepSeek** - ارزان و خوب

### برای حفظ حریم خصوصی:
✅ **LM Studio** (Local) - کاملاً آفلاین

### برای هزینه کم:
✅ **DeepSeek** - خیلی ارزان
✅ **GPT-3.5-turbo** - متعادل

---

## 📋 مثال‌های کامل

### مثال 1: استفاده از Groq (رایگان)

```bash
# در .env
LLM_API_KEY="gsk_YourGroqKeyHere"
LLM_BASE_URL="https://api.groq.com/openai/v1"
LLM_MODEL="llama-3.1-70b-versatile"
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# برای embedding از OpenAI استفاده کنید
EMBEDDING_API_KEY="sk-YourOpenAIKey"
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="text-embedding-3-small"
```

### مثال 2: کاملاً OpenAI

```bash
# در .env
LLM_API_KEY="sk-YourOpenAIKey"
LLM_BASE_URL=""
LLM_MODEL="gpt-4-turbo-preview"
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# Embedding هم OpenAI
EMBEDDING_API_KEY=""  # خالی = استفاده از LLM_API_KEY
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="text-embedding-3-large"
```

### مثال 3: Local با LM Studio

```bash
# در .env
LLM_API_KEY="not-needed"
LLM_BASE_URL="http://localhost:1234/v1"
LLM_MODEL="llama-3.1-8b-instruct"
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# Embedding از OpenAI
EMBEDDING_API_KEY="sk-YourOpenAIKey"
EMBEDDING_BASE_URL=""
EMBEDDING_MODEL="text-embedding-3-small"
```

---

## 🎉 آماده‌اید!

حالا فقط کافی است:
1. API Key بگیرید
2. در `.env` قرار دهید
3. API را restart کنید
4. تست کنید!

**سوال دارید؟** 
- چک کنید: `/home/ahad/project/core/SYSTEM_STATUS.md`
- لاگ‌ها: `tail -f logs/app.log`
