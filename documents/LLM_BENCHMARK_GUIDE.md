# راهنمای جامع Benchmark مقایسه‌ای LLM ها

## 🎯 هدف

تست و مقایسه عملکرد 8 ترکیب مختلف Provider و Model:
- **GapGPT:** gpt-4o-mini, gpt-5-mini, gpt-5.1, gpt-5.2-chat-latest
- **OpenAI:** gpt-4o-mini, gpt-4o

با اندازه‌گیری دقیق:
1. ⏱️ **زمان کل** - از ارسال درخواست تا دریافت پاسخ
2. ⚙️ **زمان پردازش** - زمان صرف شده در RAG pipeline (Qdrant + Reranker + LLM)
3. 🎫 **مصرف توکن** - تعداد توکن‌های مصرفی
4. 📚 **تعداد منابع** - چند منبع از Qdrant برگشت داده شد

---

## 📁 فایل‌های ایجاد شده

### 1. `/srv/tests/test_llm_comparison_simple.py`
اسکریپت اصلی تست که با تنظیمات فعلی `.env` کار می‌کند.

**ویژگی‌ها:**
- تست 5 سوال نمونه (برای سرعت)
- اندازه‌گیری دقیق زمان
- ذخیره نتایج در `/tmp/llm_test_*.json`

**استفاده:**
```bash
cd /srv/deployment/docker
sudo docker compose exec core-api python /app/tests/test_llm_comparison_simple.py
```

### 2. `/srv/tests/run_comprehensive_benchmark.sh`
اسکریپت bash برای تست خودکار تمام 8 ترکیب.

**ویژگی‌ها:**
- تغییر خودکار `.env`
- Restart خودکار service
- پشتیبان‌گیری و بازگردانی `.env`
- زمان تقریبی: 30-45 دقیقه

**استفاده:**
```bash
bash /srv/tests/run_comprehensive_benchmark.sh
```

### 3. `/srv/tests/analyze_benchmark_results.py`
اسکریپت تحلیل و مقایسه نتایج.

**ویژگی‌ها:**
- جدول مقایسه‌ای
- شناسایی سریع‌ترین
- شناسایی کم‌ترین مصرف توکن
- توصیه بهترین انتخاب

**استفاده:**
```bash
cd /srv/deployment/docker
sudo docker compose exec core-api python /app/tests/analyze_benchmark_results.py
```

---

## 🚀 روش اجرا

### روش 1: تست خودکار (توصیه می‌شود)

```bash
# اجرای تست کامل تمام ترکیبات
bash /srv/tests/run_comprehensive_benchmark.sh

# تحلیل نتایج
cd /srv/deployment/docker
sudo docker compose exec core-api python /app/tests/analyze_benchmark_results.py
```

**نکات مهم:**
- ⚠️ این اسکریپت `.env` را تغییر می‌دهد
- ⚠️ Service چندین بار restart می‌شود
- ⚠️ زمان کل: 30-45 دقیقه
- ✅ `.env` به حالت اولیه برمی‌گردد

---

### روش 2: تست دستی (برای کنترل بیشتر)

برای هر ترکیب Provider+Model:

#### مرحله 1: ویرایش `.env`

```bash
nano /srv/.env
```

تغییر این خطوط:
```bash
# برای GapGPT gpt-4o-mini
LLM2_MODEL="gpt-4o-mini"
LLM2_BASE_URL="https://api.gapgpt.ir/v1"
LLM2_API_KEY="your-gapgpt-key"

# یا برای OpenAI gpt-4o
LLM2_MODEL="gpt-4o"
LLM2_BASE_URL="https://api.openai.com/v1"
LLM2_API_KEY="your-openai-key"
```

#### مرحله 2: Restart Service

```bash
cd /srv/deployment/docker
sudo docker compose restart core-api
sleep 10  # صبر برای آماده شدن
```

#### مرحله 3: اجرای تست

```bash
sudo docker compose exec core-api python /app/tests/test_llm_comparison_simple.py
```

#### مرحله 4: تکرار برای تمام ترکیبات

لیست کامل ترکیبات:

| # | Provider | Model | Base URL |
|---|----------|-------|----------|
| 1 | GapGPT | gpt-4o-mini | https://api.gapgpt.ir/v1 |
| 2 | GapGPT | gpt-5-mini | https://api.gapgpt.ir/v1 |
| 3 | GapGPT | gpt-5.1 | https://api.gapgpt.ir/v1 |
| 4 | GapGPT | gpt-5.2-chat-latest | https://api.gapgpt.ir/v1 |
| 5 | OpenAI | gpt-4o-mini | https://api.openai.com/v1 |
| 6 | OpenAI | gpt-4o | https://api.openai.com/v1 |
| 7 | OpenAI | gpt-4o | https://api.openai.com/v1 |
| 8 | OpenAI | gpt-4o | https://api.openai.com/v1 |

#### مرحله 5: تحلیل نتایج

```bash
sudo docker compose exec core-api python /app/tests/analyze_benchmark_results.py
```

---

## 📊 نتایج تست نمونه

### تست فعلی (GapGPT gpt-4o)

```
✅ موفق: 5/5
⏱️  میانگین زمان کل: 9,904ms (~10 ثانیه)
⏱️  میانگین زمان پردازش: 8,785ms
🎫 میانگین توکن: 2,279
```

**تحلیل:**
- سرعت خوب (حدود 10 ثانیه)
- مصرف توکن متوسط
- نرخ موفقیت 100%

---

## 📈 فرمت خروجی

### فایل JSON نتایج (`/tmp/llm_test_*.json`)

```json
{
  "config": {
    "provider": "GapGPT",
    "model": "gpt-4o",
    "base_url": "https://api.gapgpt.app/v1"
  },
  "timestamp": "2026-02-16T05:26:41.123Z",
  "results": [
    {
      "success": true,
      "query": "مالیات بر ارزش افزوده چیست...",
      "total_time_ms": 27528,
      "processing_time_ms": 27405,
      "tokens_used": 2811,
      "sources_count": 4,
      "answer_length": 1234
    }
  ]
}
```

### گزارش مقایسه (`/tmp/benchmark_comparison_report.json`)

```json
{
  "summary": [...],
  "fastest": {
    "provider": "OpenAI",
    "model": "gpt-4o-mini",
    "avg_total_ms": 7500
  },
  "least_tokens": {
    "provider": "GapGPT",
    "model": "gpt-5-mini",
    "avg_tokens": 1800
  },
  "best_overall": {
    "provider": "OpenAI",
    "model": "gpt-4o-mini"
  }
}
```

---

## 🔍 تحلیل گلوگاه‌ها

برای تحلیل دقیق‌تر زمان هر مرحله:

```bash
# مشاهده جزئیات یک تست
cat /tmp/llm_test_gpt-4o.json | jq '.results[] | {
  query: .query[:50],
  total: .total_time_ms,
  processing: .processing_time_ms,
  network: (.total_time_ms - .processing_time_ms)
}'
```

**مراحل پردازش:**
1. **Network Overhead** = Total - Processing (~100-500ms)
2. **Processing Time** شامل:
   - Embedding query (~100ms)
   - Qdrant search (~50ms)
   - Reranker (~200ms)
   - LLM generation (~باقیمانده)

---

## 💡 توصیه‌ها

### برای سرعت بیشتر:
1. استفاده از `gpt-4o-mini` یا `gpt-5-mini`
2. کاهش `top_k` در Qdrant
3. استفاده از caching

### برای کیفیت بالاتر:
1. استفاده از `gpt-4o` یا `gpt-5.1`
2. افزایش تعداد منابع
3. بهبود prompt ها

### برای کاهش هزینه:
1. استفاده از مدل‌های mini
2. کاهش max_tokens
3. استفاده از GapGPT (ارزان‌تر از OpenAI)

---

## 🐛 عیب‌یابی

### خطا: "Timeout"
```bash
# افزایش timeout در .env
LLM_PRIMARY_TIMEOUT=30  # به جای 15
```

### خطا: "Service not available"
```bash
# بررسی وضعیت service
cd /srv/deployment/docker
sudo docker compose ps
sudo docker compose logs core-api --tail=50
```

### خطا: "API Key invalid"
```bash
# بررسی API keys در .env
grep "API_KEY" /srv/.env
```

---

## 📝 یادداشت‌های مهم

1. **تست با 20 سوال کامل:**
   - برای تست دقیق‌تر، می‌توانید `SAMPLE_QUERIES` را در اسکریپت به 20 سوال افزایش دهید
   - زمان هر تست: ~2-3 دقیقه (به جای 30-60 ثانیه)

2. **تست Qdrant و Reranker جداگانه:**
   - برای اندازه‌گیری دقیق زمان Qdrant و Reranker، از تست قبلی استفاده کنید:
   ```bash
   python /app/tests/test_business_timing_analysis.py
   ```

3. **مقایسه با تست قبلی:**
   - تست قبلی: 20 سوال با تنظیمات فعلی
   - تست جدید: 5 سوال × 8 تنظیمات
   - برای مقایسه دقیق، باید تعداد سوالات یکسان باشد

---

## 🎯 نتیجه‌گیری

این benchmark به شما کمک می‌کند:
- ✅ بهترین Provider را انتخاب کنید (GapGPT vs OpenAI)
- ✅ بهترین Model را انتخاب کنید (mini vs standard vs advanced)
- ✅ تعادل بین سرعت، کیفیت و هزینه پیدا کنید
- ✅ گلوگاه‌های سیستم را شناسایی کنید

**توصیه نهایی:** ابتدا تست خودکار را اجرا کنید، سپس بر اساس نتایج، تنظیمات بهینه را انتخاب کنید.
