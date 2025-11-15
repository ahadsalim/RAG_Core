# راهنمای استقرار سیستم RAG Core

این پوشه شامل تمام اسکریپت‌ها و فایل‌های پیکربندی برای استقرار سیستم RAG Core است.

## 📁 ساختار پوشه

```
deployment/
├── start.sh                      # اسکریپت اصلی نصب (توصیه می‌شود)
├── deploy_production.sh          # نصب production با Nginx و SSL
├── deploy_development.sh         # نصب development (local)
├── auto_dev_setup.sh            # نصب خودکار development
├── backup_manager.sh            # مدیریت کامل backup/restore
├── backup.sh                    # اسکریپت backup ساده
├── restore.sh                   # بازیابی از backup
├── rotate_secrets.sh            # تغییر خودکار رمزهای عبور
├── manage_apikey.sh             # مدیریت API keys
├── validate_env.sh              # اعتبارسنجی فایل .env
├── requirements.txt             # وابستگی‌های Python
├── requirements-minimal.txt     # وابستگی‌های حداقلی
├── config/
│   └── .env.example            # نمونه فایل تنظیمات
└── docker/
    ├── docker-compose.yml      # پیکربندی اصلی Docker
    ├── docker-compose.override.example.yml  # نمونه override برای local
    ├── Dockerfile              # Docker image
    ├── init-db.sql            # اسکریپت اولیه دیتابیس
    └── .env -> ../../.env     # symlink به .env اصلی
```

---

## 🚀 نصب سریع

### روش 1: استفاده از start.sh (توصیه می‌شود)

```bash
cd /srv/deployment
chmod +x start.sh
sudo ./start.sh
```

این اسکریپت:
- محیط را تشخیص می‌دهد (development یا production)
- فایل `.env` را از template ایجاد می‌کند
- رمزهای امن تولید می‌کند
- اسکریپت مناسب را اجرا می‌کند

### روش 2: نصب دستی Production

```bash
cd /srv/deployment
chmod +x deploy_production.sh
sudo ./deploy_production.sh
```

**نیازمندی‌ها:**
- دامنه معتبر (برای SSL)
- دسترسی root
- پورت‌های 80, 443, 81 باز

**شامل:**
- Nginx Proxy Manager با SSL خودکار
- Systemd service برای auto-start
- Firewall configuration
- Log rotation
- Monitoring setup

### روش 3: نصب Development

```bash
cd /srv/deployment
chmod +x deploy_development.sh
./deploy_development.sh
```

**برای:**
- توسعه محلی
- تست
- بدون نیاز به دامنه یا SSL

---

## 🐳 مدیریت Docker

### شروع سرویس‌ها

```bash
cd /srv/deployment/docker
docker-compose up -d
```

### توقف سرویس‌ها

```bash
docker-compose stop
```

### مشاهده لاگ‌ها

```bash
# همه سرویس‌ها
docker-compose logs -f

# یک سرویس خاص
docker-compose logs -f core-api
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
```

### بررسی وضعیت

```bash
docker-compose ps
```

### راه‌اندازی مجدد

```bash
# روش امن (جلوگیری از خطای ContainerConfig)
docker-compose stop
docker-compose rm -f
docker-compose up -d

# یا استفاده از اسکریپت
./deploy_production.sh  # یا deploy_development.sh
```

---

## 💾 Backup و Restore

### Backup خودکار

```bash
# Backup کامل
./backup_manager.sh --auto-backup

# Backup فقط database
./backup_manager.sh --backup-db

# Backup فقط فایل‌ها
./backup_manager.sh --backup-files
```

### Restore

```bash
# لیست backupها
./backup_manager.sh --list

# Restore از آخرین backup
./backup_manager.sh --restore latest

# Restore از backup خاص
./backup_manager.sh --restore /path/to/backup.tar.gz
```

### Backup دوره‌ای (Cron)

```bash
# اضافه کردن به crontab
crontab -e

# Backup روزانه ساعت 2 صبح
0 2 * * * /srv/deployment/backup_manager.sh --auto-backup
```

---

## 🔐 مدیریت امنیت

### تغییر رمزهای عبور

```bash
# تغییر خودکار همه رمزها
./rotate_secrets.sh

# تغییر دستی در .env
nano /srv/.env
# سپس restart سرویس‌ها
cd docker && docker-compose restart
```

### مدیریت API Keys

```bash
# تولید API key جدید
./manage_apikey.sh generate

# لیست API keys
./manage_apikey.sh list

# حذف API key
./manage_apikey.sh revoke <key>
```

---

## 🔧 پیکربندی

### فایل .env

فایل اصلی تنظیمات در `/srv/.env` قرار دارد.

**مهم:** هرگز `.env` را commit نکنید!

```bash
# کپی از template
cp /srv/deployment/config/.env.example /srv/.env

# ویرایش
nano /srv/.env
```

### متغیرهای مهم

```bash
# محیط
ENVIRONMENT=production  # یا development

# دامنه
DOMAIN_NAME=your-domain.com

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres-core:5432/db
POSTGRES_PASSWORD=secure-password

# Redis
REDIS_URL=redis://:password@redis-core:6379/0
REDIS_PASSWORD=secure-password

# Celery
CELERY_BROKER_URL=redis://:password@redis-core:6379/1
CELERY_RESULT_BACKEND=redis://:password@redis-core:6379/2

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Integration
INGEST_API_URL=http://ingest-api:8000
INGEST_API_KEY=your-key
USERS_API_URL=http://users-api:9000
USERS_API_KEY=your-key
```

### اعتبارسنجی .env

```bash
./validate_env.sh
```

این اسکریپت بررسی می‌کند:
- ✅ همه متغیرهای ضروری موجود باشند
- ✅ از Docker service names استفاده شده (نه localhost)
- ✅ رمزهای عبور قوی باشند
- ✅ فرمت URLها صحیح باشد

---

## 📊 سرویس‌ها و پورت‌ها

| سرویس | پورت داخلی | پورت خارجی | توضیحات |
|-------|------------|------------|---------|
| **core-api** | 7001 | 7001 | API اصلی |
| **postgres-core** | 5432 | 7433 | PostgreSQL |
| **redis-core** | 6379 | 7379 | Redis |
| **qdrant** | 6333 | 7333 | Vector DB |
| **celery-worker** | - | - | Background tasks |
| **celery-beat** | - | - | Scheduler |
| **flower** | 5555 | 5555 | Celery monitoring |
| **nginx-proxy-manager** | 80/443/81 | 80/443/81 | Reverse proxy |

### دسترسی به سرویس‌ها

```bash
# API Documentation
http://localhost:7001/docs

# Health Check
http://localhost:7001/health

# Flower (Celery monitoring)
http://localhost:5555

# Nginx Proxy Manager Admin
http://localhost:81
# Default: admin@example.com / changeme

# Qdrant Dashboard
http://localhost:7333/dashboard
```

---

## 🔍 عیب‌یابی

### خطای ContainerConfig

اگر با خطای `KeyError: 'ContainerConfig'` مواجه شدید:

```bash
cd /srv/deployment/docker
docker-compose stop
docker-compose rm -f
docker-compose up -d
```

**علت:** Docker Compose نمی‌تواند اطلاعات image قدیمی را بخواند.

**راه‌حل:** اسکریپت‌های `deploy_production.sh` و `deploy_development.sh` این مشکل را خودکار حل می‌کنند.

### سرویس‌ها start نمی‌شوند

```bash
# بررسی لاگ‌ها
docker-compose logs <service-name>

# بررسی .env
./validate_env.sh

# بررسی permissions
ls -la /srv/.env
chmod 640 /srv/.env
```

### مشکل اتصال به Database

```bash
# بررسی وضعیت
docker-compose ps postgres-core

# بررسی لاگ
docker-compose logs postgres-core

# Test اتصال
docker-compose exec postgres-core psql -U core_user -d core_db -c "SELECT 1;"
```

### Celery کار نمی‌کند

```bash
# بررسی worker
docker-compose logs celery-worker

# بررسی beat
docker-compose logs celery-beat

# بررسی Flower
http://localhost:5555

# Restart
docker-compose restart celery-worker celery-beat
```

---

## 📝 Logs

### مکان لاگ‌ها

```bash
# Docker logs
docker-compose logs

# Application logs (در container)
docker-compose exec core-api ls -la /app/logs/

# System logs
journalctl -u core-api.service
```

### Log rotation

Log rotation به صورت خودکار در `deploy_production.sh` پیکربندی می‌شود:

```
/var/log/core/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        docker-compose restart core-api
    endscript
}
```

---

## 🔄 به‌روزرسانی

### به‌روزرسانی کد

```bash
cd /srv
git pull

# Rebuild و restart
cd deployment/docker
docker-compose build --no-cache core-api celery-worker celery-beat
docker-compose stop core-api celery-worker celery-beat
docker-compose rm -f core-api celery-worker celery-beat
docker-compose up -d
```

### به‌روزرسانی dependencies

```bash
# ویرایش requirements.txt
nano /srv/deployment/requirements.txt

# Rebuild
cd /srv/deployment/docker
docker-compose build --no-cache
docker-compose up -d
```

---

## 🎯 Best Practices

### 1. همیشه از اسکریپت‌های deployment استفاده کنید
```bash
./deploy_production.sh  # نه docker-compose up -d مستقیم
```

### 2. قبل از هر تغییر backup بگیرید
```bash
./backup_manager.sh --auto-backup
```

### 3. .env را validate کنید
```bash
./validate_env.sh
```

### 4. از Docker service names استفاده کنید
```bash
# ✅ درست
DATABASE_URL=postgresql://user:pass@postgres-core:5432/db

# ❌ غلط
DATABASE_URL=postgresql://user:pass@localhost:5432/db
```

### 5. رمزهای عبور را دوره‌ای تغییر دهید
```bash
./rotate_secrets.sh
```

### 6. Monitoring را فعال نگه دارید
```bash
# Flower
http://localhost:5555

# Prometheus metrics
http://localhost:7001/metrics
```

---

## 📞 پشتیبانی

برای مشکلات و سوالات:

1. ابتدا لاگ‌ها را بررسی کنید
2. فایل `.env` را validate کنید
3. مستندات را مطالعه کنید: `/srv/document/`
4. از اسکریپت‌های عیب‌یابی استفاده کنید

---

## 📚 مستندات بیشتر

- [مستندات کامل](/srv/document/README.md)
- [راهنمای Celery](/srv/document/CELERY_IMPLEMENTATION.md)
- [راهنمای RAG Flow](/srv/document/RAG_FLOW_EXPLANATION.md)
- [راهنمای API Keys](/srv/document/API_KEYS_SETUP.md)
