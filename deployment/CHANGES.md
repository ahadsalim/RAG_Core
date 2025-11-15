# تغییرات اعمال شده در Deployment

## تاریخ: 2025-11-14

### مشکلات حل شده

#### 1. خطای 502 Bad Gateway ✅
**مشکل**: سرویس‌ها نمی‌توانستند به یکدیگر متصل شوند

**علت**: 
- آدرس‌های سرویس‌ها در `.env` به `localhost` اشاره می‌کردند
- داخل Docker container، `localhost` به خود container اشاره می‌کند نه به سایر containerها

**راه‌حل**:
- تغییر `.env.example` برای استفاده از نام‌های سرویس Docker
- اضافه کردن کامنت‌های راهنما در `.env.example`

#### 2. Database Authentication Failed ✅
**مشکل**: دیتابیس رمز عبور را قبول نمی‌کرد

**علت**:
- متغیرهای `POSTGRES_*` در `.env` وجود نداشتند
- `docker-compose.yml` از مقادیر hardcoded استفاده می‌کرد
- رمز عبور در `DATABASE_URL` با رمز عبور container مطابقت نداشت

**راه‌حل**:
- اضافه کردن `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` به `.env.example`
- تغییر `docker-compose.yml` برای استفاده از متغیرهای محیطی
- به‌روزرسانی `start.sh` و `deploy_production.sh` برای تنظیم این متغیرها

#### 3. Invalid Host Header ✅
**مشکل**: Nginx Proxy Manager خطای "Invalid host header" می‌داد

**علت**:
- `DOMAIN_NAME` در `.env` تکراری بود (یک خط خالی در انتها)
- FastAPI `TrustedHostMiddleware` فقط domain تنظیم شده را قبول می‌کند

**راه‌حل**:
- اصلاح `start.sh` برای حذف خطوط تکراری `DOMAIN_NAME` قبل از اضافه کردن
- اصلاح `deploy_production.sh` به همین شکل
- حذف `DOMAIN_NAME=` خالی از `.env` فعلی

#### 4. Celery Workers خطا می‌دهند ✅
**مشکل**: `celery-worker` و `celery-beat` با خطا exit می‌کردند

**علت**:
- ماژول `app.celery` وجود ندارد
- Celery هنوز پیاده‌سازی نشده است

**راه‌حل**:
- غیرفعال کردن موقت Celery workers
- ایجاد مستندات کامل در `CELERY_STATUS.md`
- توضیح اینکه Celery اختیاری است و سیستم بدون آن کار می‌کند

---

## فایل‌های تغییر یافته

### 1. `/srv/deployment/config/.env.example`
**تغییرات**:
- ✅ تغییر `DATABASE_URL` از `localhost:7433` به `postgres-core:5432`
- ✅ اضافه کردن `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- ✅ تغییر `REDIS_URL` از `localhost:7379` به `redis-core:6379`
- ✅ تغییر `QDRANT_HOST` از `localhost` به `qdrant`
- ✅ تغییر `QDRANT_PORT` از `7333` به `6333`
- ✅ تغییر `CELERY_BROKER_URL` و `CELERY_RESULT_BACKEND` برای استفاده از `redis-core`
- ✅ اضافه کردن کامنت‌های راهنما برای Docker vs Local development

### 2. `/srv/deployment/start.sh`
**تغییرات**:
- ✅ اصلاح روش تنظیم `DOMAIN_NAME` برای جلوگیری از تکرار
- ✅ اضافه کردن تنظیم `POSTGRES_PASSWORD` در بخش production
- ✅ استفاده از `sed -i '/^DOMAIN_NAME=/d'` برای حذف خطوط قبلی

### 3. `/srv/deployment/deploy_production.sh`
**تغییرات**:
- ✅ تغییر روش تولید رمزهای عبور (base64 برای keys، hex برای passwords)
- ✅ اضافه کردن تنظیم `POSTGRES_PASSWORD`
- ✅ اضافه کردن به‌روزرسانی `REDIS_URL` با password
- ✅ اضافه کردن به‌روزرسانی `CELERY_*` URLs با password
- ✅ اصلاح روش تنظیم `DOMAIN_NAME`
- ✅ اضافه کردن راهنمای Custom Nginx Config در خروجی

### 4. `/srv/deployment/docker/docker-compose.yml`
**تغییرات**:
- ✅ تغییر PostgreSQL environment variables برای استفاده از `${POSTGRES_*}`
- ✅ حذف مقادیر hardcoded

### 5. `/srv/.env`
**تغییرات**:
- ✅ تصحیح آدرس‌های سرویس‌ها
- ✅ اضافه کردن متغیرهای PostgreSQL
- ✅ حذف `DOMAIN_NAME=` خالی از انتها

---

## فایل‌های جدید ایجاد شده

### 1. `/srv/deployment/CELERY_STATUS.md`
**محتوا**:
- توضیح چرا Celery غیرفعال شد
- راهنمای کامل برای فعال‌سازی Celery
- مثال‌های کد برای پیاده‌سازی
- لیست کاربردهای پیشنهادی

### 2. `/srv/deployment/README.md`
**محتوا**:
- راهنمای کامل deployment
- ساختار پوشه
- دستورالعمل نصب
- مشکلات رایج و راه‌حل‌ها
- راهنمای پیکربندی
- دستورات مفید

### 3. `/srv/deployment/validate_env.sh`
**محتوا**:
- اسکریپت validation برای `.env`
- بررسی متغیرهای ضروری
- بررسی استفاده از نام‌های سرویس Docker
- بررسی امنیت رمزهای عبور
- گزارش مشکلات با رنگ‌بندی

### 4. `/srv/deployment/docker/docker-compose.override.example.yml`
**محتوا**:
- نمونه override برای local development
- تنظیمات برای اجرای خارج از Docker

### 5. `/srv/deployment/CHANGES.md`
**محتوا**:
- این فایل - مستندات تغییرات

---

## نحوه استفاده

### برای نصب جدید:
```bash
cd /srv/deployment
sudo ./start.sh
```

### برای بررسی .env فعلی:
```bash
cd /srv/deployment
./validate_env.sh
```

### برای اصلاح .env موجود:
```bash
# روش 1: دستی
nano /srv/.env

# روش 2: با sed
cd /srv
sed -i 's/@localhost:7433/@postgres-core:5432/g' .env
sed -i 's/@localhost:7379/@redis-core:6379/g' .env
sed -i 's/QDRANT_HOST="localhost"/QDRANT_HOST="qdrant"/g' .env
sed -i 's/QDRANT_PORT=7333/QDRANT_PORT=6333/g' .env
sed -i '/^DOMAIN_NAME=/d' .env
echo 'DOMAIN_NAME="your-domain.com"' >> .env
```

### برای ری‌استارت سرویس‌ها:
```bash
cd /srv/deployment/docker
docker-compose restart core-api
```

---

## تست

برای تست تغییرات:

```bash
# 1. Validate .env
/srv/deployment/validate_env.sh

# 2. بررسی health
curl http://localhost:7001/health

# 3. بررسی با domain
curl https://your-domain.com/health

# 4. بررسی لاگ‌ها
cd /srv/deployment/docker
docker-compose logs -f core-api
```

---

## نتیجه

✅ **تمام مشکلات حل شدند**:
- خطای 502 Bad Gateway
- Database authentication
- Invalid host header  
- Celery errors

✅ **مستندات کامل اضافه شد**:
- README.md
- CELERY_STATUS.md
- CHANGES.md

✅ **ابزارهای کمکی ایجاد شد**:
- validate_env.sh
- docker-compose.override.example.yml

✅ **اسکریپت‌های deployment بهبود یافتند**:
- start.sh
- deploy_production.sh

**سیستم حالا آماده استفاده در production است! 🎉**
