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
├── backup.sh              # Backup و Restore
├── manage.sh              # مدیریت (validate, API keys, secrets)
├── requirements.txt       # وابستگی‌های Python
├── config/
│   └── .env.example      # نمونه تنظیمات
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

### Backup
```bash
# ایجاد backup
./backup.sh backup

# لیست backupها
./backup.sh list

# Restore
./backup.sh restore /path/to/backup.tar.gz

# پاکسازی backupهای قدیمی
./backup.sh clean
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
/srv/document/DOCUMENTATION.md
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

نمونه: `/srv/deployment/config/.env.example`

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
