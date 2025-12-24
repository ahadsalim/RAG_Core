# راهنمای استقرار سیستم RAG Core

## 🚀 نصب سریع

```bash
cd /srv/deployment
chmod +x deploy.sh
sudo ./deploy.sh
```

---

## 📁 ساختار

```
deployment/
├── deploy.sh              # اسکریپت نصب
├── start.sh               # راه‌اندازی سرویس‌ها
├── backup_auto.sh         # بکآپ خودکار (هر 6 ساعت)
├── backup_manual.sh       # بکآپ دستی و Restore
├── manage.sh              # مدیریت (validate, API keys, secrets)
├── requirements.txt       # وابستگی‌های Python
├── .env.example           # نمونه تنظیمات
└── docker/
    ├── docker-compose.yml # فایل Docker Compose
    ├── Dockerfile
    └── init-db.sql
```

---

## 🔧 دستورات

### نصب
```bash
./deploy.sh
```

### بکآپ خودکار
```bash
# اجرای یکبار بکآپ
./backup_auto.sh run

# فعال‌سازی cron (هر 6 ساعت)
./backup_auto.sh setup

# غیرفعال‌سازی cron
./backup_auto.sh remove

# نمایش وضعیت
./backup_auto.sh status

# تست اتصال SSH
./backup_auto.sh test
```

### بکآپ دستی
```bash
# منوی تعاملی
./backup_manual.sh

# بکآپ کامل (DB + Qdrant + Config)
./backup_manual.sh backup full

# بکآپ فقط دیتابیس
./backup_manual.sh backup db

# ریستور کامل
./backup_manual.sh restore full /path/to/backup.tar.gz

# ریستور دیتابیس
./backup_manual.sh restore db /path/to/backup.sql.gz

# لیست بکآپ‌ها
./backup_manual.sh list
```

### مدیریت
```bash
# منوی مدیریت
./manage.sh

# شامل:
# - اعتبارسنجی .env
# - مدیریت API Keys (Ingest, Users)
# - تغییر رمزهای عبور (Rotate Secrets)
```

### مدیریت سرویس‌ها
```bash
cd docker

# شروع
docker-compose up -d

# توقف
docker-compose stop

# لاگ‌ها
docker-compose logs -f

# راه‌اندازی مجدد
docker-compose restart
```

---

## 📚 مستندات کامل

مستندات کامل در:
```
/srv/documents/DOCUMENTATION.md
```

---

## 🔗 دسترسی

- API Docs: http://localhost:7001/docs
- Health: http://localhost:7001/health
- Flower: http://localhost:5555
- Nginx: http://localhost:81

---

## ⚙️ پیکربندی

فایل تنظیمات: `/srv/.env`

نمونه: `/srv/deployment/.env.example`

---

## 🆘 پشتیبانی

```bash
# بررسی سلامت
curl http://localhost:7001/health

# مشاهده لاگ‌ها
cd docker && docker-compose logs -f

# اعتبارسنجی .env
./manage.sh  # انتخاب گزینه 1
```

---

# 🔐 راهنمای تنظیم بکآپ خودکار

این راهنما نحوه تنظیم بکآپ خودکار به سرور پشتیبان را توضیح می‌دهد.

---

## 📋 پیش‌نیازها

1. **سرور پشتیبان**: یک VPS برای نگهداری بکآپ‌ها
2. **دسترسی SSH**: دسترسی root به سرور پشتیبان
3. **فضای دیسک کافی**: حداقل 50GB در سرور پشتیبان

---

## 📝 نکات مهم

### ⏰ نگهداری بکآپ‌ها:

- **بکآپ‌های محلی**: حداکثر 3 روز (برای صرفه‌جویی در فضای دیسک)
- **بکآپ‌های سرور پشتیبان**: 30 روز (قابل تنظیم در `.env`)

### 🔐 محتویات بکآپ خودکار (هر 6 ساعت):

1. **PostgreSQL Database** - تمام داده‌های سیستم
2. **Redis Data** - Cache و Session‌ها
3. **Qdrant Vector Data** - داده‌های Embedding
4. **NPM Data** - تنظیمات Nginx Proxy Manager
5. **فایل .env** - تنظیمات محیطی

### 🔐 محتویات بکآپ کامل (دستی):

1. **PostgreSQL Database** - تمام داده‌های سیستم
2. **Qdrant Vector Data** - داده‌های Embedding (مهم!)
3. **NPM Data** - تنظیمات Nginx Proxy Manager
4. **فایل .env** - تنظیمات محیطی

---

## 🔧 مرحله 1: تنظیم SSH Key

### در سرور اصلی (Production):

```bash
# 1. ایجاد SSH Key برای بکآپ (ED25519 - سریع و امن)
ssh-keygen -t ed25519 -f /root/.ssh/backup_key -N ""

# 2. نمایش Public Key
cat /root/.ssh/backup_key.pub
```

**خروجی را کپی کنید** (شبیه این):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGx... root@production
```

### در سرور پشتیبان (Backup Server):

```bash
# 1. ایجاد پوشه برای بکآپ‌ها
mkdir -p /backups/core
chmod 755 /backups/core

# 2. اضافه کردن Public Key
mkdir -p /root/.ssh
nano /root/.ssh/authorized_keys
```

**Public Key کپی شده را در فایل `authorized_keys` paste کنید**

```bash
# 3. تنظیم دسترسی‌ها
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
```

### تست اتصال SSH:

```bash
# در سرور اصلی
ssh -i /root/.ssh/backup_key root@BACKUP_SERVER_IP

# اگر بدون پرسیدن رمز وارد شدید، موفق بوده‌اید!
exit
```

---

## ⚙️ مرحله 2: تنظیم Environment Variables

### در سرور اصلی:

```bash
# ویرایش فایل .env
nano /srv/.env
```

**اضافه کردن تنظیمات زیر:**

```env
# ===========================
# Backup Server Configuration
# ===========================
BACKUP_SERVER_HOST=YOUR_BACKUP_SERVER_IP
BACKUP_SERVER_USER=root
BACKUP_SERVER_PATH=/backups/core
BACKUP_SSH_KEY=/root/.ssh/backup_key
BACKUP_RETENTION_DAYS=30
BACKUP_KEEP_LOCAL=false
```

**جایگزین کنید:**
- `YOUR_BACKUP_SERVER_IP` → IP یا hostname سرور پشتیبان شما

---

## 🕐 مرحله 3: فعال‌سازی بکآپ خودکار

```bash
# تست اتصال
./backup_auto.sh test

# فعال‌سازی cron job (هر 6 ساعت)
./backup_auto.sh setup

# بررسی وضعیت
./backup_auto.sh status
```

### تست دستی:

```bash
# اجرای دستی برای تست
./backup_auto.sh run

# بررسی لاگ
tail -f /var/log/core_backup.log
```

---

## 📊 مرحله 4: بررسی بکآپ‌ها

### در سرور اصلی:

```bash
# مشاهده بکآپ‌های محلی
ls -lh /var/lib/core/backups/auto/

# مشاهده لاگ بکآپ
tail -20 /var/log/core_backup.log

# وضعیت کامل
./backup_auto.sh status
```

### در سرور پشتیبان:

```bash
# مشاهده بکآپ‌های دریافتی
ls -lh /backups/core/

# بررسی حجم
du -sh /backups/core/
```

---

## 🛠️ استفاده از اسکریپت‌های بکآپ

### 1️⃣ بکآپ خودکار (backup_auto.sh)

**اجرا می‌شود:** هر 6 ساعت توسط cron

**عملکرد:**
- بکآپ PostgreSQL + Redis + Qdrant + NPM Config + .env
- فشرده‌سازی
- انتقال به سرور پشتیبان با rsync
- پاکسازی بکآپ‌های قدیمی

**دستورات:**
```bash
./backup_auto.sh run      # اجرای یکبار
./backup_auto.sh setup    # فعال‌سازی cron
./backup_auto.sh remove   # غیرفعال‌سازی cron
./backup_auto.sh status   # نمایش وضعیت
./backup_auto.sh test     # تست اتصال SSH
```

---

### 2️⃣ بکآپ دستی (backup_manual.sh)

**اجرا می‌شود:** توسط شما به صورت دستی

#### 🔹 منوی تعاملی:
```bash
./backup_manual.sh
```

#### 🔹 بکآپ کامل:
```bash
./backup_manual.sh backup full
```
**محل ذخیره:** `/var/lib/core/backups/manual/core_full_YYYYMMDD_HHMMSS.tar.gz`

#### 🔹 بکآپ فقط دیتابیس:
```bash
./backup_manual.sh backup db
```
**محل ذخیره:** `/var/lib/core/backups/manual/core_db_YYYYMMDD_HHMMSS.sql.gz`

#### 🔹 ریستور کامل:
```bash
./backup_manual.sh restore full /path/to/backup.tar.gz
```

#### 🔹 ریستور دیتابیس:
```bash
./backup_manual.sh restore db /path/to/backup.sql.gz
```

#### 🔹 لیست بکآپ‌ها:
```bash
./backup_manual.sh list
```

---

## 🔍 عیب‌یابی

### مشکل 1: خطای SSH Connection

```bash
# تست اتصال SSH
ssh -i /root/.ssh/backup_key -v root@BACKUP_SERVER_IP

# بررسی دسترسی‌های کلید
ls -la /root/.ssh/backup_key
# باید: -rw------- (600)

# اصلاح دسترسی
chmod 600 /root/.ssh/backup_key
```

### مشکل 2: بکآپ انتقال نمی‌یابد

```bash
# بررسی لاگ
tail -50 /var/log/core_backup.log

# تست rsync دستی
rsync -avz -e "ssh -i /root/.ssh/backup_key" \
    /var/lib/core/backups/auto/ \
    root@BACKUP_SERVER_IP:/backups/core/
```

### مشکل 3: فضای دیسک کم

```bash
# بررسی فضای دیسک
df -h

# پاکسازی بکآپ‌های قدیمی محلی
find /var/lib/core/backups -name "*.tar.gz" -mtime +7 -delete
find /var/lib/core/backups -name "*.sql.gz" -mtime +7 -delete
```

### مشکل 4: Cron اجرا نمی‌شود

```bash
# بررسی وضعیت cron
systemctl status cron

# بررسی cron jobs
crontab -l

# بررسی لاگ cron
grep CRON /var/log/syslog | tail -20

# تست دستی
./backup_auto.sh run
```

---

## 📞 دستورات مفید

```bash
# مشاهده تمام بکآپ‌ها
ls -lh /var/lib/core/backups/auto/
ls -lh /var/lib/core/backups/manual/

# حجم کل بکآپ‌ها
du -sh /var/lib/core/backups/

# جدیدترین بکآپ
ls -lt /var/lib/core/backups/auto/*.tar.gz 2>/dev/null | head -1

# وضعیت بکآپ
./backup_auto.sh status

# پاکسازی بکآپ‌های بیش از 30 روز
find /var/lib/core/backups -name "*.tar.gz" -mtime +30 -delete
```

---

## ✅ چک‌لیست راه‌اندازی

- [ ] SSH Key ایجاد شد (`ssh-keygen -t ed25519 -f /root/.ssh/backup_key -N ""`)
- [ ] Public Key به سرور پشتیبان اضافه شد
- [ ] اتصال SSH بدون رمز تست شد (`./backup_auto.sh test`)
- [ ] متغیرهای محیطی در `.env` تنظیم شدند
- [ ] بکآپ دستی تست شد (`./backup_auto.sh run`)
- [ ] بکآپ در سرور پشتیبان بررسی شد
- [ ] Cron job فعال شد (`./backup_auto.sh setup`)

---

**نسخه**: 2.0  
**آخرین بروزرسانی**: 2024-12-24
