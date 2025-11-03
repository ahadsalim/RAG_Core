# راهنمای تنظیم API Keys و Tokens

## محل‌های ذخیره‌سازی کلیدهای API

### 1. فایل `.env` برای Development

در محیط توسعه، کلیدهای API را در فایل `.env` قرار دهید:

```bash
cd /home/ahad/project/core
cp deployment/config/.env.example .env
```

سپس فایل `.env` را ویرایش کنید:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxx  # کلید API OpenAI خود را اینجا قرار دهید
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Anthropic Configuration (اختیاری)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx  # اگر از Claude استفاده می‌کنید

# Cohere Configuration (برای Reranking - اختیاری)
COHERE_API_KEY=xxxxxxxxxxxxxxxxxxxxx  # برای بهبود reranking

# Hugging Face (برای مدل‌های محلی - اختیاری)
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxx

# API Keys برای ارتباط بین سیستم‌ها
INGEST_API_KEY=your-secure-ingest-api-key  # برای دسترسی به Ingest
USERS_API_KEY=your-secure-users-api-key    # برای دسترسی از Users
```

### 2. فایل `.env.production` برای Production

برای محیط production، از فایل جداگانه استفاده کنید:

```bash
cp deployment/config/.env.example .env.production
# ویرایش با کلیدهای production
nano .env.production
```

### 3. متغیرهای محیطی سیستم‌عامل

برای امنیت بیشتر در production، می‌توانید از متغیرهای محیطی سیستم استفاده کنید:

```bash
# در ~/.bashrc یا ~/.profile
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxx"
export CORE_JWT_SECRET="your-very-secure-jwt-secret"
```

### 4. Docker Secrets (توصیه شده برای Production)

```yaml
# docker-compose.yml
version: '3.8'
services:
  core-api:
    secrets:
      - openai_api_key
      - jwt_secret
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

ایجاد فایل‌های secret:
```bash
mkdir -p secrets
echo "sk-xxxxxxxxxxxxxxxxxxxxxx" > secrets/openai_api_key.txt
openssl rand -hex 32 > secrets/jwt_secret.txt
chmod 600 secrets/*
```

### 5. استفاده از Key Management Services (برای Enterprise)

برای محیط‌های enterprise از سرویس‌های مدیریت کلید استفاده کنید:

- **AWS Secrets Manager**
- **Azure Key Vault**
- **Google Secret Manager**
- **HashiCorp Vault**

مثال برای AWS Secrets Manager:
```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# در settings.py
secrets = get_secret('core-api-keys')
OPENAI_API_KEY = secrets.get('openai_api_key')
```

## دریافت API Keys

### OpenAI
1. به [platform.openai.com](https://platform.openai.com) بروید
2. ثبت نام/ورود کنید
3. به بخش API Keys بروید
4. کلید جدید ایجاد کنید

### Anthropic (Claude)
1. به [console.anthropic.com](https://console.anthropic.com) بروید
2. ثبت نام برای دسترسی API
3. کلید API دریافت کنید

### Cohere
1. به [dashboard.cohere.ai](https://dashboard.cohere.ai) بروید
2. ثبت نام رایگان
3. کلید API دریافت کنید

### مدل‌های محلی (رایگان)
برای استفاده از مدل‌های محلی:
```bash
# نصب Ollama
curl -fsSL https://ollama.com/install.sh | sh

# دانلود مدل
ollama pull llama2
ollama pull mistral

# در .env
LOCAL_MODEL_URL=http://localhost:11434
LOCAL_MODEL_NAME=llama2
```

## چک‌لیست امنیتی

### ✅ موارد ضروری

- [ ] هرگز کلیدهای API را در Git commit نکنید
- [ ] فایل `.env` را به `.gitignore` اضافه کنید
- [ ] برای هر محیط (dev/staging/prod) کلید جداگانه استفاده کنید
- [ ] دسترسی به فایل‌های حاوی کلید را محدود کنید (chmod 600)
- [ ] کلیدها را به صورت دوره‌ای rotate کنید

### ❌ کارهایی که نباید انجام دهید

- کلیدها را در کد hardcode نکنید
- کلیدها را در لاگ‌ها print نکنید
- کلیدها را در URL یا Query Parameters ارسال نکنید
- از کلیدهای تست در production استفاده نکنید

## تست کلیدها

برای تست صحت کلیدها:

```python
# scripts/test_api_keys.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def test_openai():
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        print("✅ OpenAI API key is valid")
        return True
    except Exception as e:
        print(f"❌ OpenAI API key is invalid: {e}")
        return False

if __name__ == "__main__":
    test_openai()
```

اجرا:
```bash
python scripts/test_api_keys.py
```

## مانیتورینگ استفاده

برای مانیتور استفاده از API:

1. **OpenAI Dashboard**: مشاهده مصرف در [platform.openai.com/usage](https://platform.openai.com/usage)

2. **تنظیم محدودیت‌ها**:
```python
# در settings.py
OPENAI_MONTHLY_LIMIT = 100  # دلار
OPENAI_DAILY_LIMIT = 10     # دلار
```

3. **لاگ و مانیتورینگ محلی**:
```python
# در RAG pipeline
logger.info(f"API call: model={model}, tokens={tokens}, cost=${cost}")
```

## پشتیبانی چند Provider

برای استفاده از چندین provider:

```python
# در .env
PRIMARY_LLM_PROVIDER=openai
FALLBACK_LLM_PROVIDER=anthropic

# Failover strategy
LLM_PROVIDERS_PRIORITY=openai,anthropic,local
```
