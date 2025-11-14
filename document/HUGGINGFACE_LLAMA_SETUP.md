# راهنمای استفاده از Llama-3.1-8B-Instruct با Hugging Face

## دریافت توکن Hugging Face

### مرحله 1: ایجاد حساب کاربری
1. به https://huggingface.co بروید
2. روی "Sign Up" کلیک کنید
3. حساب کاربری ایجاد کنید

### مرحله 2: ایجاد Access Token
1. بعد از ورود، به Settings بروید: https://huggingface.co/settings/tokens
2. روی "New token" کلیک کنید
3. نام توکن را وارد کنید (مثلاً: "core-llama-token")
4. نوع را "Read" انتخاب کنید
5. "Generate token" را کلیک کنید
6. توکن را کپی کنید (فقط یکبار نمایش داده می‌شود!)

### مرحله 3: درخواست دسترسی به Llama
1. به صفحه مدل بروید: https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
2. روی "Request Access" کلیک کنید
3. فرم را پر کنید و شرایط را بپذیرید
4. معمولاً ظرف چند دقیقه تایید می‌شود

## تنظیم در Core System

### روش 1: از طریق فایل .env

```bash
cd /home/ahad/project/core

# ویرایش فایل .env
nano .env

# اضافه کردن این خطوط:
HUGGINGFACE_API_KEY="hf_xxxxxxxxxxxxxxxxxxxxxxxxxx"
HUGGINGFACE_MODEL="meta-llama/Llama-3.1-8B-Instruct"
ACTIVE_LLM_PROVIDER="huggingface"
```

### روش 2: در زمان اجرای start.sh

وقتی `start.sh` اجرا می‌شود، اگر `.env` وجود نداشته باشد، از شما می‌پرسد.

## مدل‌های Llama موجود

### Llama 3.1 Series
```bash
# 8B - سریع و کارآمد (توصیه می‌شود)
HUGGINGFACE_MODEL="meta-llama/Llama-3.1-8B-Instruct"

# 70B - قدرتمند‌تر اما کندتر
HUGGINGFACE_MODEL="meta-llama/Llama-3.1-70B-Instruct"

# 405B - بسیار قدرتمند (نیاز به GPU قوی)
HUGGINGFACE_MODEL="meta-llama/Llama-3.1-405B-Instruct"
```

### Llama 3 Series
```bash
# 8B
HUGGINGFACE_MODEL="meta-llama/Meta-Llama-3-8B-Instruct"

# 70B
HUGGINGFACE_MODEL="meta-llama/Meta-Llama-3-70B-Instruct"
```

## مدل‌های فارسی/چندزبانه

```bash
# mGPT - پشتیبانی فارسی
HUGGINGFACE_MODEL="ai-forever/mGPT"

# Aya - چندزبانه با فارسی
HUGGINGFACE_MODEL="CohereForAI/aya-101"

# ParsGPT - فارسی
HUGGINGFACE_MODEL="HooshvareLab/gpt2-fa"
```

## تست عملکرد

### تست از Command Line

```bash
# با curl
curl -X POST http://localhost:7001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون کار ایران چیست؟",
    "language": "fa"
  }'
```

### تست از Python

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

### تست از رابط کاربری

```bash
firefox /home/ahad/project/users/index.html
```

## محدودیت‌ها و نکات

### Rate Limiting
- Hugging Face Inference API محدودیت درخواست دارد
- سرویس رایگان: ~30,000 کاراکتر/روز
- برای استفاده بیشتر، به PRO یا Enterprise نیاز دارید

### Cold Start
- اولین بار که مدل صدا زده می‌شود، ممکن است 20-30 ثانیه طول بکشد
- بعد از بارگذاری، سریع‌تر می‌شود

### مدل Loading
اگر خطای 503 دریافت کردید:
```
Model is loading. Please retry in a few seconds.
```
این طبیعی است. 30 ثانیه صبر کنید و دوباره امتحان کنید.

## بهینه‌سازی برای فارسی

### تنظیمات توصیه شده

```bash
# در .env
HUGGINGFACE_TEMPERATURE=0.7
HUGGINGFACE_MAX_TOKENS=2048

# برای پاسخ‌های طولانی‌تر
HUGGINGFACE_MAX_TOKENS=4096
```

### System Prompt فارسی

مدل به خوبی فارسی را می‌فهمد. در API می‌توانید system prompt فارسی بدهید:

```json
{
  "query": "سوال شما",
  "language": "fa",
  "system_prompt": "شما یک دستیار حقوقی هستید که به فارسی پاسخ می‌دهید."
}
```

## استفاده از مدل محلی (بدون Hugging Face API)

اگر می‌خواهید Llama را محلی اجرا کنید:

### با Ollama
```bash
# نصب Ollama
curl -fsSL https://ollama.com/install.sh | sh

# دانلود Llama 3.1
ollama pull llama3.1

# تنظیمات در .env
LOCAL_LLM_URL="http://localhost:11434"
LOCAL_LLM_MODEL="llama3.1"
ACTIVE_LLM_PROVIDER="local"
```

### با LlamaCpp
```bash
# نصب llama-cpp-python
pip install llama-cpp-python

# دانلود مدل GGUF
wget https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf

# استفاده در Core (نیاز به کد اضافی)
```

## مقایسه عملکرد

| Provider | کیفیت | سرعت | هزینه | فارسی |
|----------|--------|------|--------|-------|
| OpenAI GPT-4 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 💰💰💰 | ⭐⭐⭐⭐⭐ |
| Llama-3.1-8B (HF) | ⭐⭐⭐⭐ | ⭐⭐⭐ | 💰 (رایگان محدود) | ⭐⭐⭐⭐ |
| Llama-3.1-70B (HF) | ⭐⭐⭐⭐⭐ | ⭐⭐ | 💰💰 | ⭐⭐⭐⭐⭐ |
| Llama محلی | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 💰 (هاردور) | ⭐⭐⭐ |

## عیب‌یابی

### خطا: "Invalid API key"
```bash
# چک کنید توکن صحیح است
echo $HUGGINGFACE_API_KEY

# باید با hf_ شروع شود
```

### خطا: "Access denied to model"
- مطمئن شوید درخواست دسترسی به Llama را تایید کرده‌اید
- به https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct بروید
- اگر "Gated model" می‌بینید، باید درخواست بدهید

### خطا: Rate limit exceeded
```bash
# از cache استفاده کنید
ENABLE_SEMANTIC_CACHE=true

# یا به plan بالاتر upgrade کنید
```

### پاسخ‌های ضعیف
```bash
# Temperature را کم کنید برای دقت بیشتر
HUGGINGFACE_TEMPERATURE=0.3

# یا زیاد کنید برای خلاقیت بیشتر
HUGGINGFACE_TEMPERATURE=0.9
```

## لینک‌های مفید

- **Hugging Face Hub**: https://huggingface.co
- **Llama Models**: https://huggingface.co/meta-llama
- **API Docs**: https://huggingface.co/docs/api-inference
- **Pricing**: https://huggingface.co/pricing
- **Persian Models**: https://huggingface.co/models?language=fa

## پشتیبانی

برای مشکلات:
1. لاگ‌ها را چک کنید: `docker-compose logs -f core-api`
2. API را تست کنید: `curl http://localhost:7001/health`
3. مستندات را بخوانید: `/document/API_KEYS_SETUP.md`
