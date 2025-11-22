# خلاصه تغییرات مهاجرت به e5-large (1024d)

## تاریخ: 2025-11-22

## تغییرات اعمال شده

### 1. فایل‌های کد تغییر یافته

#### `/srv/app/services/qdrant_service.py`
- ✅ تنظیمات collection برای پشتیبانی از 1024 بعد
- ✅ تغییر `large` از 1536 به 1024
- ✅ اضافه شدن `xlarge` برای 1536 بعد

#### `/srv/app/services/sync_service.py`
- ✅ بروزرسانی `_get_vector_field_by_dim()` برای mapping صحیح
- ✅ 1024d → `large`
- ✅ 1536d → `xlarge`

#### `/srv/app/rag/pipeline.py`
- ✅ بروزرسانی `_get_vector_field()` برای mapping صحیح
- ✅ همسان‌سازی با sync_service

### 2. اسکریپت‌های جدید

#### `/srv/scripts/reset_qdrant_collection.py`
- ✅ حذف ایمن collection با تایید کاربر
- ✅ ایجاد مجدد با تنظیمات جدید
- ✅ نمایش آمار و راهنمای مراحل بعدی

### 3. مستندات بروزرسانی شده

#### `/srv/document/2_INGEST_SYSTEM_API_GUIDE.md`
- ✅ تغییر dimension از 768 به 1024
- ✅ تغییر مدل از e5-base به e5-large
- ✅ بروزرسانی مثال‌ها و validation

#### `/srv/document/EMBEDDING_CONFIGURATION_GUIDE.md`
- ✅ بروزرسانی جدول vector fields
- ✅ تاکید بر e5-large برای 1024d

#### `/srv/document/E5_LARGE_MIGRATION_GUIDE.md` (جدید)
- ✅ راهنمای کامل مهاجرت گام‌به‌گام
- ✅ troubleshooting و rollback plan
- ✅ checklist و best practices

## Vector Field Mapping (جدید)

```
Dimension → Vector Field
512       → small
768       → medium
1024      → large    ← e5-large
1536      → xlarge   ← OpenAI models
3072      → default
```

## مراحل اجرا برای مهاجرت

### مرحله 1: Core System
```bash
cd /srv
python scripts/reset_qdrant_collection.py
```

### مرحله 2: Ingest System
```bash
# تنظیم .env
EMBEDDING_MODEL="intfloat/multilingual-e5-large"
EMBEDDING_DIM=1024

# Re-embed
python manage.py re_embed_all_chunks --model intfloat/multilingual-e5-large

# Sync
python manage.py sync_to_core --full --batch-size 100
```

### مرحله 3: تایید
```bash
# بررسی وضعیت
curl -X GET http://core-api:7001/api/v1/sync/status \
  -H "X-API-Key: ${INGEST_API_KEY}"
```

## تاثیرات

### مثبت ✅
- کیفیت بهتر embeddings (e5-large قدرتمندتر از e5-base)
- پشتیبانی از مدل‌های مختلف با dimensions متفاوت
- سازگاری با استانداردهای جدید

### منفی ⚠️
- نیاز به re-embed تمام داده‌ها
- افزایش حجم ذخیره‌سازی (~33% بیشتر: 1024 vs 768)
- کمی کندتر در embedding (e5-large بزرگتر است)

## وضعیت فعلی

- ✅ کد Core System آماده است
- ✅ Qdrant collection باید reset شود
- ⏳ Ingest system باید تنظیم و re-embed کند
- ⏳ Full sync به Core انجام شود

## نکات مهم

1. **قبل از reset Qdrant، backup بگیرید** (اختیاری ولی توصیه می‌شود)
2. **Ingest system باید با e5-large تنظیم شود** قبل از sync
3. **تمام chunks باید re-embed شوند** با مدل جدید
4. **Vector dimension باید 1024 باشد** نه 768

## تست‌های پیشنهادی

```bash
# 1. تست Python syntax
python3 -m py_compile app/services/qdrant_service.py
python3 -m py_compile app/services/sync_service.py
python3 -m py_compile app/rag/pipeline.py
python3 -m py_compile scripts/reset_qdrant_collection.py

# 2. تست Qdrant connection
python3 << EOF
from app.services.qdrant_service import QdrantService
qdrant = QdrantService()
print("Qdrant connected:", qdrant.client.get_collections())
EOF

# 3. تست vector field mapping
python3 << EOF
from app.services.sync_service import SyncService
sync = SyncService()
print("768d →", sync._get_vector_field_by_dim(768))   # medium
print("1024d →", sync._get_vector_field_by_dim(1024)) # large
print("1536d →", sync._get_vector_field_by_dim(1536)) # xlarge
EOF
```

## مراجع

- راهنمای کامل: `/srv/document/E5_LARGE_MIGRATION_GUIDE.md`
- API Guide: `/srv/document/2_INGEST_SYSTEM_API_GUIDE.md`
- Embedding Config: `/srv/document/EMBEDDING_CONFIGURATION_GUIDE.md`

---

**وضعیت:** آماده برای اجرا  
**اولویت:** بالا  
**زمان تخمینی:** 2-4 ساعت (بسته به حجم داده)
