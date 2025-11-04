# یادداشت‌های استقرار (Deployment Notes)

## تاریخ: 2025-11-04

### مشکلات حل شده

#### 1. خطای 502 Bad Gateway
**علت:** 
- متغیرهای محیطی Celery نادرست بودند
- خطای syntax در `DATABASE_URL` (دو `""` در انتها)
- `CELERY_RESULT_BACKEND` در docker-compose تعریف نشده بود

**راه‌حل:**
- اصلاح فرمت URLها در `.env`
- اضافه کردن `CELERY_RESULT_BACKEND` به environment variables
- Restart کردن سرویس‌ها

#### 2. Celery Workers
**وضعیت:** غیرفعال شدند چون در کد استفاده نمی‌شوند
- `celery-worker`: Commented out
- `celery-beat`: Commented out  
- `flower`: Commented out

**نکته:** اگر در آینده نیاز به background tasks شد، باید:
1. فایل `app/celery.py` ایجاد شود
2. Uncomment کردن سرویس‌ها در `docker-compose.yml`

---

## وضعیت امنیتی رمزها

### ✅ رمزهای قوی:
- `SECRET_KEY`: 64 کاراکتر Base64
- `JWT_SECRET_KEY`: 64 کاراکتر Base64
- `QDRANT_API_KEY`: 64 کاراکتر
- `REDIS_PASSWORD`: 32 کاراکتر
- `INGEST_API_KEY`: 64 کاراکتر Base64
- `USERS_API_KEY`: 64 کاراکتر Base64

### ⚠️ رمزهای ضعیف (نیاز به تغییر):
- `S3_ACCESS_KEY_ID`: "minioadmin" (default)
- `S3_SECRET_ACCESS_KEY`: "minioadmin" (default)

**توصیه:** اگر از MinIO استفاده می‌کنید، رمزها را تغییر دهید.

---

## سرویس‌های فعال

```
✅ core-api           - FastAPI application (port 7001)
✅ nginx-proxy-manager - Reverse proxy (ports 80, 443, 81)
✅ postgres-core      - PostgreSQL database (port 7433)
✅ redis-core         - Redis cache (port 7379)
✅ qdrant             - Vector database (ports 7333, 7334)
```

---

## دستورات مفید

### شروع سرویس‌ها
```bash
cd /srv
docker-compose -f deployment/docker/docker-compose.yml up -d
```

### مشاهده لاگ‌ها
```bash
docker logs core-api --tail 50
docker logs nginx-proxy-manager --tail 50
```

### بررسی وضعیت
```bash
docker ps
curl -s https://core.arpanet.ir/api/v1/health
```

### Restart سرویس خاص
```bash
docker-compose -f deployment/docker/docker-compose.yml restart core-api
```

---

## نصب مجدد

اگر می‌خواهید از ابتدا نصب کنید:

1. Clone کردن repository
2. کپی کردن `.env.example` به `.env`:
   ```bash
   cp deployment/config/.env.example .env
   ```
3. تنظیم رمزها و متغیرهای محیطی در `.env`
4. اجرای docker-compose:
   ```bash
   docker-compose -f deployment/docker/docker-compose.yml up -d
   ```

**نکته مهم:** 
- فایل `.env` در git commit نمی‌شود، پس باید دستی ایجاد شود
- فایل template در `deployment/config/.env.example` موجود است

---

## مشکلات شناخته شده

### Qdrant Unhealthy
وضعیت: `unhealthy` در healthcheck
- سرویس کار می‌کند اما healthcheck ممکن است fail شود
- نیاز به بررسی بیشتر دارد

---

## تماس و پشتیبانی

- Domain: https://core.arpanet.ir
- Admin Panel (Nginx): http://core.arpanet.ir:81
- API Docs: https://core.arpanet.ir/docs (فقط در development mode)
