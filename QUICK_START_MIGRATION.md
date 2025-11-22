# راهنمای سریع مهاجرت به e5-large

## دستورات سریع

### 1️⃣ Reset Qdrant (Core System)
```bash
cd /srv
python scripts/reset_qdrant_collection.py
# پاسخ: yes
```

### 2️⃣ تنظیم Ingest System
```bash
# در .env فایل Ingest:
EMBEDDING_MODEL="intfloat/multilingual-e5-large"
EMBEDDING_DIM=1024
```

### 3️⃣ Re-embed در Ingest
```bash
python manage.py re_embed_all_chunks --model intfloat/multilingual-e5-large
```

### 4️⃣ Sync به Core
```bash
python manage.py sync_to_core --full --batch-size 100
```

### 5️⃣ تایید
```bash
curl -X GET http://core-api:7001/api/v1/sync/status \
  -H "X-API-Key: ${INGEST_API_KEY}"
```

## چک‌لیست ✅

- [ ] Core system کد جدید دارد
- [ ] `python scripts/reset_qdrant_collection.py` اجرا شد
- [ ] Ingest با e5-large تنظیم شد
- [ ] Re-embed انجام شد
- [ ] Full sync موفق بود
- [ ] تست جستجو کار می‌کند

## مشکلات رایج

### Dimension mismatch
```bash
# مطمئن شوید EMBEDDING_DIM=1024 در Ingest
```

### Vector field error
```bash
# Restart Core system
docker-compose restart core-api
```

## مستندات کامل

📖 `/srv/document/E5_LARGE_MIGRATION_GUIDE.md`
