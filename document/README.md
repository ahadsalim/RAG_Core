# راهنمای استقرار (Deployment Guide)

این پوشه شامل تمام اسکریپت‌ها و فایل‌های پیکربندی برای استقرار سیستم RAG Core است.

## 📁 ساختار پوشه

```
deployment/
├── start.sh                      # اسکریپت اصلی نصب (توصیه می‌شود)
├── deploy_production.sh          # نصب production
├── deploy_development.sh         # نصب development
├── auto_dev_setup.sh            # نصب خودکار development
├── backup_manager.sh            # مدیریت backup
├── backup.sh                    # اسکریپت backup
├── restore.sh                   # بازیابی از backup
├── rotate_secrets.sh            # تغییر رمزهای عبور
├── manage_apikey.sh             # مدیریت API keys
├── config/
│   ├── .env.example            # نمونه فایل تنظیمات
│   └── ports.md                # مستندات پورت‌ها
├── docker/
│   ├── docker-compose.yml      # پیکربندی Docker
│   ├── Dockerfile              # Docker image
│   ├── init-db.sql            # اسکریپت اولیه دیتابیس
│   └── .env -> ../../.env     # symlink به .env اصلی
├── CELERY_STATUS.md            # وضعیت و راهنمای Celery
└── README.md                   # این فایل
```

## 🚀 نصب سریع

### روش 1: استفاده از start.sh (توصیه می‌شود)

```bash
cd /srv/deployment
chmod +x start.sh
sudo ./start.sh
```

این اسکریپت:
- فایل `.env` را ایجاد می‌کند
- رمزهای عبور امن تولید می‌کند
- domain name را می‌پرسد
- محیط production را راه‌اندازی می‌کند
- تمام سرویس‌ها را start می‌کند

### روش 2: نصب دستی

```bash
# 1. کپی فایل .env
cp deployment/config/.env.example .env

# 2. ویرایش .env و تنظیم مقادیر
nano .env

# 3. اجرای docker-compose
cd deployment/docker
docker-compose up -d
```

## ⚙️ تنظیمات مهم

### متغیرهای محیطی برای Docker

در فایل `.env`، آدرس‌های سرویس‌ها باید به نام‌های Docker service اشاره کنند:

```bash
# ✅ صحیح (برای Docker)
DATABASE_URL="postgresql+asyncpg://core_user:password@postgres-core:5432/core_db"
REDIS_URL="redis://:password@redis-core:6379/0"
QDRANT_HOST="qdrant"
QDRANT_PORT=6333

# ❌ اشتباه (برای Docker)
DATABASE_URL="postgresql+asyncpg://core_user:password@localhost:7433/core_db"
REDIS_URL="redis://:password@localhost:7379/0"
QDRANT_HOST="localhost"
QDRANT_PORT=7333
```

### متغیرهای PostgreSQL

این متغیرها برای docker-compose ضروری هستند:

```bash
POSTGRES_DB=core_db
POSTGRES_USER=core_user
POSTGRES_PASSWORD=your-secure-password
```

### DOMAIN_NAME

برای production، حتماً domain را تنظیم کنید:

```bash
DOMAIN_NAME="core.example.com"
```

**نکته مهم**: فقط یک خط `DOMAIN_NAME` در `.env` داشته باشید. اسکریپت‌های نصب خطوط تکراری را حذف می‌کنند.

## 🔧 مشکلات رایج و راه‌حل

### مشکل 1: خطای 502 Bad Gateway

**علت**: آدرس‌های سرویس‌ها به `localhost` اشاره می‌کنند

**راه‌حل**:
```bash
# ویرایش .env
sed -i 's/@localhost:7433/@postgres-core:5432/g' .env
sed -i 's/@localhost:7379/@redis-core:6379/g' .env
sed -i 's/QDRANT_HOST="localhost"/QDRANT_HOST="qdrant"/g' .env
sed -i 's/QDRANT_PORT=7333/QDRANT_PORT=6333/g' .env

# ری‌استارت سرویس‌ها
cd deployment/docker
docker-compose restart core-api
```

### مشکل 2: Database authentication failed

**علت**: رمز عبور در `.env` با رمز عبور در Docker volume مطابقت ندارد

**راه‌حل**:
```bash
# حذف volume قدیمی و ایجاد مجدد
cd deployment/docker
docker-compose stop postgres-core
docker-compose rm -f postgres-core
docker volume rm docker_postgres-core-data
docker-compose up -d postgres-core
```

### مشکل 3: Invalid host header

**علت**: `DOMAIN_NAME` در `.env` تنظیم نشده یا تکراری است

**راه‌حل**:
```bash
# حذف خطوط تکراری
sed -i '/^DOMAIN_NAME=/d' .env
# اضافه کردن domain صحیح
echo 'DOMAIN_NAME="core.example.com"' >> .env
# ری‌استارت
cd deployment/docker
docker-compose restart core-api
```

### مشکل 4: Celery workers خطا می‌دهند

**علت**: Celery هنوز پیاده‌سازی نشده است

**راه‌حل**: Celery اختیاری است. برای غیرفعال کردن:
```bash
cd deployment/docker
docker-compose stop celery-worker celery-beat
```

برای اطلاعات بیشتر: [CELERY_STATUS.md](./CELERY_STATUS.md)

## 📊 بررسی وضعیت سرویس‌ها

```bash
# وضعیت همه سرویس‌ها
cd deployment/docker
docker-compose ps

# لاگ‌های یک سرویس
docker-compose logs -f core-api

# بررسی health
curl http://localhost:7001/health
curl https://your-domain.com/health
```

## 🔐 امنیت

### تولید رمزهای عبور امن

اسکریپت‌های نصب به طور خودکار رمزهای عبور امن تولید می‌کنند:

```bash
# SECRET_KEY و JWT_SECRET: base64 (48 bytes)
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')

# Database و Redis passwords: hex (24 bytes)
# از hex استفاده می‌شود تا کاراکترهای خاص در URL مشکل ایجاد نکنند
DB_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)
```

### تغییر رمزهای عبور

```bash
cd deployment
./rotate_secrets.sh
```

## 🌐 پیکربندی Nginx Proxy Manager

1. دسترسی به Admin UI: `http://YOUR_SERVER_IP:81`
   - Email: `admin@example.com`
   - Password: `changeme`

2. تغییر رمز عبور

3. اضافه کردن Proxy Host:
   - Domain Names: `core.example.com`
   - Scheme: `http`
   - Forward Hostname/IP: `core-api`
   - Forward Port: `7001`
   - ✅ Websockets Support
   - ✅ Block Common Exploits

4. درخواست SSL Certificate:
   - SSL tab → Request new certificate
   - Email: your-email@example.com
   - ✅ Force SSL
   - ✅ HTTP/2 Support
   - ✅ HSTS Enabled

## 💾 Backup و Restore

### ایجاد Backup

```bash
cd deployment
./backup_manager.sh --auto-backup
```

### بازیابی از Backup

```bash
cd deployment
./restore.sh /path/to/backup.tar.gz
```

### Backup خودکار (Cron)

```bash
crontab -e
# اضافه کردن:
0 2 * * * /srv/deployment/backup_manager.sh --auto-backup
```

## 📝 لاگ‌ها

```bash
# لاگ‌های Docker
cd deployment/docker
docker-compose logs -f

# لاگ‌های یک سرویس خاص
docker-compose logs -f core-api
docker-compose logs -f postgres-core
docker-compose logs -f redis-core

# لاگ‌های Nginx Proxy Manager
docker-compose logs -f nginx-proxy-manager
```

## 🔄 به‌روزرسانی

```bash
# دریافت آخرین تغییرات
git pull

# ری‌بیلد و ری‌استارت
cd deployment/docker
docker-compose build --no-cache
docker-compose up -d --force-recreate
```

## 🧪 تست

```bash
# Health check
curl http://localhost:7001/health

# با domain
curl https://core.example.com/health

# API Documentation
curl https://core.example.com/docs

# Metrics
curl http://localhost:7001/metrics
```

## 📚 مستندات بیشتر

- [CELERY_STATUS.md](./CELERY_STATUS.md) - وضعیت و راهنمای Celery
- [config/ports.md](./config/ports.md) - لیست پورت‌ها
- [../document/](../document/) - مستندات کامل پروژه

## ❓ سوالات متداول

### چرا از نام‌های سرویس Docker استفاده می‌کنیم؟

زمانی که containerها در یک Docker network هستند، می‌توانند با نام سرویس به یکدیگر متصل شوند. `localhost` به خود container اشاره می‌کند، نه به سایر containerها.

### آیا می‌توانم خارج از Docker اجرا کنم?

بله، اما باید آدرس‌ها را به `localhost` تغییر دهید و پورت‌های exposed را استفاده کنید:
- PostgreSQL: `localhost:7433`
- Redis: `localhost:7379`
- Qdrant: `localhost:7333`

### Celery اجباری است؟

خیر، Celery اختیاری است. سیستم بدون Celery کامل کار می‌کند.

## 🆘 پشتیبانی

اگر مشکلی دارید:

1. لاگ‌ها را بررسی کنید
2. فایل `.env` را بررسی کنید
3. وضعیت سرویس‌ها را چک کنید
4. مستندات را مطالعه کنید

برای گزارش باگ یا درخواست feature، issue ایجاد کنید.
