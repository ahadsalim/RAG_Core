# 🔄 دستورالعمل Sync مجدد

**تاریخ:** 2025-11-22 06:10 UTC  
**وضعیت:** ✅ آماده برای دریافت داده

---

## ✅ کارهای انجام شده

1. ✅ **Qdrant پاک شد**
   - Collection قدیمی حذف شد (4305 نقطه)
   - Collection جدید با 0 نقطه ایجاد شد
   - تنظیمات 1024d فعال است

2. ✅ **گزارشات پاک شدند**
   - گزارشات تست قدیمی حذف شدند
   - اسکریپت‌های موقت پاک شدند

3. ✅ **سیستم آماده است**
   - Auto-detection فعال
   - API endpoint کار می‌کند
   - Monitoring آماده است

---

## 🚀 مراحل Sync از Ingest

### 1. شروع Sync
سیستم Ingest باید 4304 بردار را ارسال کند به:
```
POST http://localhost:7001/api/v1/sync/embeddings
```

### 2. نظارت بر پیشرفت
در یک ترمینال جداگانه:
```bash
bash scripts/monitor_sync.sh
```

این اسکریپت به صورت real-time پیشرفت را نشان می‌دهد:
```
Points: 1250 / 4304 (29.0%) | Status: green
```

### 3. تایید نهایی
بعد از اتمام sync:
```bash
docker exec core-api python scripts/verify_after_sync.py
```

---

## 📊 اسکریپت‌های موجود

### پاکسازی (انجام شده)
```bash
docker exec core-api python scripts/clean_for_resync.py
```

### نظارت (در حین sync)
```bash
bash scripts/monitor_sync.sh
```

### تایید سریع (بعد از sync)
```bash
docker exec core-api python scripts/verify_after_sync.py
```

### گزارش کامل (بعد از sync)
```bash
docker exec core-api python scripts/detailed_sync_report.py
```

---

## 🔍 بررسی دستی

### تعداد نقاط فعلی:
```bash
curl -s http://localhost:7333/collections/legal_documents | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['result']['points_count'])"
```

خروجی فعلی: **0** ✅

### لاگ‌های sync:
```bash
docker-compose -f deployment/docker/docker-compose.yml logs -f core-api | \
  grep "Auto-detected\|Synced"
```

### وضعیت collection:
```bash
curl -s http://localhost:7333/collections/legal_documents | python3 -m json.tool
```

---

## ✨ ویژگی‌های فعال

### Auto-Detection
سیستم خودکار dimension را تشخیص می‌دهد:
- ✅ 1024d → `large` field (e5-large)
- ✅ 768d → `medium` field
- ✅ 1536d → `xlarge` field

### Batch Processing
- حداکثر 1000 embedding در هر request
- پردازش batch به صورت خودکار
- گزارش تعداد sync شده

### Error Handling
- بررسی API key
- بررسی یکسان بودن dimensions
- خطاهای واضح و قابل فهم

---

## 📈 انتظارات

پس از sync کامل:

| متریک | مقدار مورد انتظار |
|-------|-------------------|
| تعداد نقاط | 4304 |
| Vector field | large (100%) |
| Dimension | 1024 |
| Status | green |
| Metadata | کامل |

---

## 🎯 Checklist بعد از Sync

- [ ] تعداد نقاط = 4304
- [ ] همه از vector field `large` استفاده می‌کنند
- [ ] Metadata کامل است
- [ ] جستجو کار می‌کند
- [ ] Collection status = green

---

## 🆘 عیب‌یابی

### اگر تعداد مطابقت ندارد:
```bash
# بررسی لاگ‌های خطا
docker-compose -f deployment/docker/docker-compose.yml logs core-api | grep -i error

# بررسی نمونه داده‌ها
docker exec core-api python scripts/check_qdrant_data.py
```

### اگر dimension اشتباه است:
```bash
# بررسی vector fields
curl -s http://localhost:7333/collections/legal_documents | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['result']['config']['params']['vectors'])"
```

### اگر API خطا می‌دهد:
```bash
# تست API
curl -X POST http://localhost:7001/api/v1/sync/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-Key: l6EyAgdxSjN8FBr0MGgmeQddv2LRLojDyXlV5BNGYmDn04dXd83Z3dCx/1cpoauq" \
  -d '{"embeddings": [], "sync_type": "incremental"}'
```

---

## 📝 یادداشت‌ها

- Collection با تنظیمات بهینه ایجاد شده است
- نیازی به restart کانتینرها نیست
- Auto-detection به صورت خودکار کار می‌کند
- فقط Ingest باید sync را شروع کند

---

**وضعیت فعلی:** ✅ READY  
**منتظر:** Sync از Ingest System  
**تعداد مورد انتظار:** 4304 بردار  
**Endpoint:** `POST /api/v1/sync/embeddings`
