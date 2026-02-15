# تست‌های عملکرد LLM

این پوشه شامل اسکریپت‌ها و نتایج تست‌های جامع عملکرد مدل‌های LLM است.

## 📁 ساختار فایل‌ها

### اسکریپت‌های تست
- `test_stage1_classification.py` - تست کلاسیفیکیشن (15 سوال × 2 مدل × 2 منبع)
- `test_stage2_general.py` - تست سوالات عمومی (20 سوال × 4 مدل × 2 منبع)
- `test_stage3_business_rag.py` - تست سوالات تخصصی با RAG (20 سوال)

### نتایج تست
- `test_results_stage1_classification.json` - نتایج خام مرحله 1
- `test_results_stage2_general.json` - نتایج خام مرحله 2
- `test_results_stage3_business_rag.json` - نتایج خام مرحله 3 (پس از اجرا)

### ابزارهای کمکی
- `generate_final_report.py` - تولید گزارش نهایی از نتایج
- `create_stage1_results.py` - ایجاد فایل نتایج مرحله 1

## 🚀 نحوه اجرا

### مرحله 1: تست کلاسیفیکیشن
```bash
sudo docker cp tests/test_stage1_classification.py core-api:/srv/
sudo docker exec core-api python /srv/test_stage1_classification.py
sudo docker cp core-api:/tmp/test_results_stage1_classification.json tests/
```

### مرحله 2: تست سوالات عمومی
```bash
sudo docker cp tests/test_stage2_general.py core-api:/srv/
sudo docker exec core-api python /srv/test_stage2_general.py
sudo docker cp core-api:/tmp/test_results_stage2_general.json tests/
```

### مرحله 3: تست سوالات تخصصی با RAG
```bash
sudo docker cp tests/test_stage3_business_rag.py core-api:/srv/
sudo docker exec core-api python /srv/test_stage3_business_rag.py
sudo docker cp core-api:/tmp/test_results_stage3_business_rag.json tests/
```

### تولید گزارش نهایی
```bash
python3 tests/generate_final_report.py
```

## 📊 نتایج تست‌ها

گزارش کامل در `/srv/LLM_Performance_Report.md` موجود است.

### خلاصه نتایج (فوریه 2026)

#### بهترین مدل‌ها
- **کلاسیفیکیشن:** gpt-4o-mini (OpenAI) - 1387ms، 100% موفقیت
- **سوالات عمومی:** gpt-4o-mini (OpenAI) - 3856ms، 95% موفقیت
- **سوالات تخصصی:** gpt-4o-mini (GapGPT primary، OpenAI fallback)

#### مقایسه OpenAI vs GapGPT
- **سرعت:** GapGPT 5.9% سریعتر
- **پایداری:** OpenAI 12% قابل‌اعتمادتر (91% vs 79.3%)

## ⚠️ توجه

این تست‌ها مستقیماً با API های OpenAI و GapGPT ارتباط برقرار می‌کنند و نیاز به API key معتبر دارند.
