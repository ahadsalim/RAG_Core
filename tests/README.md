# 🧪 سیستم تست جامع LLM

سیستم یکپارچه برای تست و مقایسه مدل‌های LLM با قابلیت تست تمام ترکیبات providers، models، و query types.

## � فایل‌های اصلی

### 🎯 سیستم تست جدید (توصیه می‌شود)

- **`llm_test_config.py`** - تنظیمات مرکزی (providers، models، سوالات تست)
- **`llm_benchmark_unified.py`** - سیستم تست جامع و یکپارچه
- **`llm_benchmark_analyzer.py`** - تحلیلگر نتایج و تولید گزارش

### 📊 نتایج و مستندات

- **`LLM_TEST_RESULTS.md`** - تاریخچه کامل نتایج تست‌ها
- **`benchmark_results/`** - پوشه نتایج JSON و گزارش‌های تحلیلی

---

## 🚀 راهنمای استفاده سریع

### 1️⃣ لیست مدل‌های موجود

```bash
python3 tests/llm_benchmark_unified.py --list-models
```

### 2️⃣ تست سریع (Quick Test)

```bash
# تست سریع LLM2 (سوالات تجاری)
python3 tests/llm_benchmark_unified.py --config quick --llm-type llm2

# تست سریع LLM1 (سوالات عمومی)
python3 tests/llm_benchmark_unified.py --config quick --llm-type llm1

# تست سریع Classification
python3 tests/llm_benchmark_unified.py --config quick --llm-type classification
```

### 3️⃣ تست استاندارد

```bash
# تست کامل با سوالات متنوع
python3 tests/llm_benchmark_unified.py --config standard --llm-type llm2
```

### 4️⃣ تست جامع (Comprehensive)

```bash
# تست تمام ترکیبات providers × models × queries
python3 tests/llm_benchmark_unified.py --config comprehensive --llm-type llm2
```

### 5️⃣ تست کیفیت (Quality)

```bash
# مقایسه کیفیت پاسخ‌های مدل‌های مختلف
python3 tests/llm_benchmark_unified.py --config quality --llm-type llm2
```

### 6️⃣ تست زمان‌سنجی (Timing)

```bash
# تست سرعت و زمان پاسخ‌دهی
python3 tests/llm_benchmark_unified.py --config timing --llm-type llm2
```

---

## 🎛️ تنظیمات پیشرفته

### تست provider خاص

```bash
# فقط GapGPT
python3 tests/llm_benchmark_unified.py --config standard --providers gapgpt

# فقط OpenAI
python3 tests/llm_benchmark_unified.py --config standard --providers openai

# هر دو
python3 tests/llm_benchmark_unified.py --config standard --providers gapgpt openai
```

### تست مدل‌های خاص

```bash
# تست مدل‌های مشخص
python3 tests/llm_benchmark_unified.py --config standard \
  --models gpt-4o-mini gpt-5-mini

# تست یک مدل خاص از یک provider
python3 tests/llm_benchmark_unified.py --config standard \
  --providers gapgpt --models gpt-5-mini
```

### تغییر مسیر خروجی

```bash
python3 tests/llm_benchmark_unified.py --config standard \
  --output-dir my_custom_results
```

---

## 📊 تحلیل نتایج

### مشاهده خلاصه آخرین تست

```bash
python3 tests/llm_benchmark_analyzer.py
```

### تحلیل فایل خاص

```bash
python3 tests/llm_benchmark_analyzer.py \
  --result-file benchmark_results/results_standard_llm2_20260216_070000.json
```

### تولید گزارش Markdown

```bash
python3 tests/llm_benchmark_analyzer.py --generate-report
```

### تولید گزارش با نام دلخواه

```bash
python3 tests/llm_benchmark_analyzer.py --generate-report \
  --output my_analysis_report.md
```

---

## 🔧 افزودن Provider یا Model جدید

### 1. ویرایش `llm_test_config.py`

```python
PROVIDERS = {
    'my_new_provider': {
        'name': 'My New Provider',
        'base_url': 'https://api.mynewprovider.com/v1',
        'api_key_env': 'MY_PROVIDER_API_KEY',
        'models': [
            'model-1',
            'model-2',
        ]
    }
}
```

### 2. اضافه کردن API Key به `.env`

```bash
MY_PROVIDER_API_KEY="your-api-key-here"
```

### 3. اجرای تست

```bash
python3 tests/llm_benchmark_unified.py --config standard \
  --providers my_new_provider
```

---

## � افزودن سوالات تست جدید

ویرایش `llm_test_config.py` و اضافه کردن به `TEST_QUERIES`:

```python
TEST_QUERIES = {
    'my_new_category': [
        {
            'id': 'custom_1',
            'category': 'دسته‌بندی من',
            'query': 'سوال تست من'
        },
    ]
}
```

---

## 📈 نتایج تست‌های قبلی

### فوریه 2026 - تست جامع

**توصیه‌های نهایی:**
- **Classification:** `gapgpt/gpt-4o-mini` (1387ms، 100% موفقیت)
- **LLM1 (General):** `gapgpt/gpt-4o-mini` (سریع و کارآمد)
- **LLM2 (Business):** `gapgpt/gpt-5-mini` (تعادل بهینه کیفیت/قیمت، امتیاز 8.7/10)
- **Fallback:** `openai/gpt-4o-mini` (پایداری بالا)

**مقایسه کیفیت مدل‌های GapGPT:**
- `gpt-4o-mini`: 7.9/10 (سریع، ارزان)
- `gpt-5-mini`: 8.7/10 ⭐ (بهترین تعادل)
- `gpt-5.2-chat-latest`: 9.5/10 (بالاترین کیفیت، گران‌تر)

جزئیات کامل در `LLM_TEST_RESULTS.md`

---

## 🗂️ ساختار فایل‌های خروجی

```
benchmark_results/
├── results_standard_llm2_20260216_070000.json    # نتایج خام
├── summary_standard_llm2_20260216_070000.json    # خلاصه آماری
└── report_20260216_070000.md                     # گزارش تحلیلی
```

---

## ⚠️ نکات مهم

1. **API Keys:** اطمینان حاصل کنید که API key های لازم در `.env` تنظیم شده‌اند
2. **Rate Limits:** برای تست‌های جامع، محدودیت‌های API را در نظر بگیرید
3. **زمان اجرا:** تست comprehensive می‌تواند چندین ساعت طول بکشد
4. **فضای دیسک:** نتایج JSON می‌توانند حجیم باشند (خصوصاً برای تست‌های جامع)

---

## 📚 مستندات بیشتر

- `LLM_TEST_RESULTS.md` - تاریخچه کامل نتایج تست‌ها
- `llm_test_config.py` - داکیومنت تنظیمات و سوالات
- گزارش‌های تحلیلی در `benchmark_results/`
