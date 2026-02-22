# راهنمای اتصال سرور به Cache Server
> این فایل برای AI assistant سرورهای RAG نوشته شده است.
> هدف: پیکربندی کامل یک سرور Ubuntu 24.04 برای کار بدون اینترنت بین‌الملل، با استفاده از سرور کش مرکزی.

---

## اطلاعات پایه

```
CACHE_SERVER = 10.10.10.111
```

| سرویس | پورت | کاربرد |
|-------|------|---------|
| Docker Hub mirror | `:5001` | images از `docker.io` |
| ghcr.io mirror | `:5002` | images از `ghcr.io` |
| quay.io mirror | `:5003` | images از `quay.io` |
| gcr.io mirror | `:5004` | images از `gcr.io` |
| k8s mirror | `:5005` | images از `registry.k8s.io` |
| PyPI (devpi) | `:3141` | Python packages |
| npm (verdaccio) | `:4873` | Node.js packages |
| apt cache (HTTP) | `:3142` | Ubuntu/Debian apt packages (فقط HTTP) |
| apt cache (HTTPS) | `:3144` | Ubuntu/Debian apt packages (HTTP + HTTPS tunneling) |
| apk cache | `:3143` | Alpine Linux apk packages |
| GPG keys / status | `:80` | کلیدها و وضعیت |

---

## مرحله ۰ — بلافاصله بعد از نصب Ubuntu (قبل از هر چیز)

```bash
# هدایت apt به cache سرور
# پورت 3142: فقط HTTP repositories (Ubuntu base)
# پورت 3144: HTTP + HTTPS tunneling (Docker repository)
echo 'Acquire::http::Proxy "http://10.10.10.111:3142";' | sudo tee /etc/apt/apt.conf.d/00proxy
echo 'Acquire::https::Proxy "http://10.10.10.111:3144";' | sudo tee -a /etc/apt/apt.conf.d/00proxy

# تست
sudo apt-get update
```

**توضیح پورت‌ها:**
- **پورت 3142** (از طریق nginx): فقط برای HTTP repositories مثل Ubuntu base packages
- **پورت 3144** (مستقیم apt-cacher-ng): برای HTTPS repositories مثل Docker - پشتیبانی از CONNECT tunneling

### برای Alpine Linux containers:

اگر از Alpine-based Docker images استفاده می‌کنید (مثل `nginx:alpine`, `redis:alpine`, `postgres:alpine`):

```dockerfile
# در Dockerfile یا در container:
RUN echo "http://10.10.10.111:3143/alpine/v3.19/main" > /etc/apk/repositories && \
    echo "http://10.10.10.111:3143/alpine/v3.19/community" >> /etc/apk/repositories && \
    apk update && apk upgrade
```

یا در runtime:

```bash
docker run -it alpine:latest sh
# داخل container:
echo "http://10.10.10.111:3143/alpine/v3.19/main" > /etc/apk/repositories
echo "http://10.10.10.111:3143/alpine/v3.19/community" >> /etc/apk/repositories
apk update
apk add curl vim
```

---

## مرحله ۱ — نصب Docker (کاملاً بدون اینترنت)

```bash
# پیش‌نیازها
sudo apt-get install -y ca-certificates curl gnupg

# Docker GPG key — از سرور کش (نه اینترنت)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL http://10.10.10.111/keys/docker.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Docker repo — از طریق apt-cacher-ng
# توجه: Docker repository از HTTPS استفاده می‌کند
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

# نصب
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

**نکته مهم:** Docker repository از HTTPS استفاده می‌کند. پورت 3144 از CONNECT tunneling پشتیبانی می‌کند و این مشکل را حل می‌کند.

---

## مرحله ۲ — پیکربندی Docker daemon

فایل `/etc/docker/daemon.json` را بساز:

```bash
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": ["http://10.10.10.111:5001"],
  "insecure-registries": [
    "10.10.10.111:5001",
    "10.10.10.111:5002",
    "10.10.10.111:5003",
    "10.10.10.111:5004",
    "10.10.10.111:5005"
  ]
}
EOF
sudo systemctl restart docker
```

> **`registry-mirrors`** یعنی وقتی `docker pull nginx:alpine` می‌زنی، Docker اول از `10.10.10.111:5001` چک می‌کند.
> اما این فقط برای Docker Hub کار می‌کند. برای بقیه registry‌ها باید آدرس image را عوض کنی (مرحله ۳).

---

## مرحله ۳ — تغییر آدرس images در docker-compose.yml و Dockerfile

### جدول تبدیل آدرس‌ها

| آدرس اصلی | آدرس کش | مثال |
|-----------|---------|------|
| `python:3.11-slim` | `10.10.10.111:5001/library/python:3.11-slim` | Docker Hub official |
| `postgres:15-alpine` | `10.10.10.111:5001/library/postgres:15-alpine` | Docker Hub official |
| `qdrant/qdrant:latest` | `10.10.10.111:5001/qdrant/qdrant:latest` | Docker Hub user/image |
| `ghcr.io/org/img:tag` | `10.10.10.111:5002/org/img:tag` | ghcr.io |
| `quay.io/org/img:tag` | `10.10.10.111:5003/org/img:tag` | quay.io |
| `gcr.io/org/img:tag` | `10.10.10.111:5004/org/img:tag` | gcr.io |
| `registry.k8s.io/img` | `10.10.10.111:5005/img` | k8s |

**قانون کلی:**
- Docker Hub official (بدون `/`): اضافه کن `library/` — مثلاً `nginx:alpine` → `10.10.10.111:5001/library/nginx:alpine`
- Docker Hub user/image (با `/`): فقط آدرس را عوض کن — مثلاً `qdrant/qdrant:latest` → `10.10.10.111:5001/qdrant/qdrant:latest`
- بقیه registry‌ها: پیشوند registry را با آدرس کش عوض کن

### مثال docker-compose.yml

```yaml
services:
  app:
    image: 10.10.10.111:5001/library/python:3.11-slim

  db:
    image: 10.10.10.111:5001/pgvector/pgvector:pg16

  redis:
    image: 10.10.10.111:5001/library/redis:7-alpine

  rabbitmq:
    image: 10.10.10.111:5001/library/rabbitmq:3-management-alpine

  qdrant:
    image: 10.10.10.111:5001/qdrant/qdrant:latest

  minio:
    image: 10.10.10.111:5001/minio/minio:latest

  node-exporter:
    image: 10.10.10.111:5003/prometheus/node-exporter:latest

  postgres-exporter:
    image: 10.10.10.111:5003/prometheuscommunity/postgres-exporter:latest

  cadvisor:
    image: 10.10.10.111:5001/zcube/cadvisor:latest
```

> **نکته:** `gcr.io/cadvisor/cadvisor` از طریق proxy بلاک است. به جای آن از `zcube/cadvisor` در Docker Hub استفاده کن.

### مثال Dockerfile

```dockerfile
FROM 10.10.10.111:5001/library/python:3.11-slim

# pip از cache
RUN pip install --no-cache-dir \
    --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
    --trusted-host 10.10.10.111 \
    -r requirements.txt
```

---

## مرحله ۴ — پیکربندی pip

### روش الف: فایل `pip.conf` (دائمی برای همه کاربران)

```bash
sudo tee /etc/pip.conf << 'EOF'
[global]
index-url = http://10.10.10.111:3141/root/pypi/+simple/
trusted-host = 10.10.10.111
EOF
```

### روش ب: در Dockerfile یا docker-compose build args

```dockerfile
ARG PIP_INDEX_URL=http://10.10.10.111:3141/root/pypi/+simple/
ARG PIP_TRUSTED_HOST=10.10.10.111
RUN pip install -r requirements.txt
```

```yaml
# docker-compose.yml
services:
  app:
    build:
      args:
        PIP_INDEX_URL: "http://10.10.10.111:3141/root/pypi/+simple/"
        PIP_TRUSTED_HOST: "10.10.10.111"
```

### روش ج: نصب packages آفلاین (sentence-transformers)

برای packages بزرگی که نیاز به نصب کامل آفلاین دارند (مثل `sentence-transformers`):

**مرحله 1: دانلود packages از سرور کش**
```bash
# ایجاد دایرکتوری برای packages
mkdir -p ~/offline-packages
cd ~/offline-packages

# دانلود همه فایل‌های wheel
wget -r -np -nH --cut-dirs=1 -R "index.html*" http://10.10.10.111/pypi-offline/
```

**مرحله 2: نصب از فایل‌های local**
```bash
pip install sentence-transformers==5.2.3 \
  --no-index \
  --find-links ~/offline-packages/pypi-offline/
```

در Dockerfile:

```dockerfile
FROM 10.10.10.111:5001/library/python:3.11-slim

# کپی فایل‌های wheel به container
COPY offline-packages/pypi-offline /tmp/pypi-offline

# نصب از فایل‌های local
RUN pip install --no-cache-dir \
    --no-index \
    --find-links /tmp/pypi-offline/ \
    sentence-transformers==5.2.3
```

**لیست packages آفلاین موجود:**
- `sentence-transformers==5.2.3` + همه dependencies (66 packages، ~4GB)
- شامل: `torch==2.10.0`, `transformers==5.2.0`, `numpy`, `scipy`, `scikit-learn`, `Pillow`, `nltk` و تمام CUDA packages
- دانلود: `http://10.10.10.111/pypi-offline/`

---

## مرحله ۵ — پیکربندی npm

```bash
# دائمی
npm config set registry http://10.10.10.111:4873

# یا فایل .npmrc در root پروژه
echo "registry=http://10.10.10.111:4873" > .npmrc
```

در Dockerfile:

```dockerfile
FROM 10.10.10.111:5001/library/node:20-alpine
RUN npm config set registry http://10.10.10.111:4873
COPY package*.json ./
RUN npm ci
```

---

## رفتار کش — چه اتفاقی می‌افتد اگر چیزی نباشد؟

| سرویس | اگر در کش باشد | اگر در کش نباشد |
|-------|---------------|-----------------|
| **Docker images** | ✅ از کش سرو می‌شود | ❌ خطای `not found` — باید به سرور کش اطلاع داده شود |
| **pip packages** | ✅ از کش سرو می‌شود | ✅ اگر اینترنت داشته باشد خودش می‌رود می‌گیرد |
| **npm packages** | ✅ از کش سرو می‌شود | ✅ اگر اینترنت داشته باشد خودش می‌رود می‌گیرد |
| **apt packages** | ✅ از کش سرو می‌شود | ✅ اگر اینترنت داشته باشد خودش می‌رود می‌گیرد |

**Docker image نداشت؟** روی سرور کش (`10.10.10.111`) اجرا کن:

```bash
sudo bash /srv/deployment/cache-manager.sh
# گزینه ۲ را انتخاب کن → نام image را وارد کن
```

یا مستقیم:

```bash
sudo bash /srv/deployment/cache-manager.sh add-image <image:tag>
```

---

## تست اتصال

```bash
# Docker Hub
docker pull 10.10.10.111:5001/library/redis:7-alpine

# quay.io
docker pull 10.10.10.111:5003/prometheus/node-exporter:latest

# pip (packages عادی)
pip install requests \
  --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
  --trusted-host 10.10.10.111

# apt
sudo apt-get update && sudo apt-get install -y curl

# وضعیت سرور کش
curl http://10.10.10.111/
```

---

## اگر image جدیدی نیاز داشتی که در کش نبود

**روش ۱ — فوری:** روی سرور کش اجرا کن:
```bash
sudo bash /srv/deployment/cache-manager.sh add-image <image:tag>
```

**روش ۲ — دائمی:** image را به لیست اضافه کن تا هر شب خودکار کش شود:
```bash
# روی سرور کش، فایل را ویرایش کن:
nano /srv/deployment/cache-manager.sh warmup-images
# image را به آرایه IMAGES اضافه کن
# شب بعد ساعت ۲ صبح خودکار کش می‌شود
```

**روش ۳ — با منوی تعاملی:**
```bash
sudo bash /srv/deployment/cache-manager.sh
```

---

## اگر Python package جدیدی نیاز داشتی

pip به صورت pull-through کار می‌کند — اگر اینترنت داشته باشد خودش می‌رود می‌گیرد و کش می‌کند.
اگر می‌خواهی از قبل کش کنی:

```bash
# روی سرور کش:
sudo bash /srv/deployment/cache-manager.sh
# گزینه ۳ را انتخاب کن
```

---

## لیست کامل images موجود در کش

برای دیدن همه images کش‌شده:

```bash
# روی سرور کش:
sudo bash /srv/deployment/cache-manager.sh
# گزینه 5 را انتخاب کن

# یا مستقیم:
curl -s http://10.10.10.111:5001/v2/_catalog   # Docker Hub
curl -s http://10.10.10.111:5003/v2/_catalog   # quay.io
```

---

# 📚 مرجع کامل موارد کش شده

## 🐳 Docker Images (به تفکیک Registry)

### Docker Hub (پورت 5001)

**Base Images:**
- `10.10.10.111:5001/library/python:3.11-slim`
- `10.10.10.111:5001/library/ubuntu:24.04`
- `10.10.10.111:5001/library/node:20-alpine`

**Databases:**
- `10.10.10.111:5001/library/postgres:15-alpine`
- `10.10.10.111:5001/library/postgres:16-alpine`
- `10.10.10.111:5001/pgvector/pgvector:pg16`
- `10.10.10.111:5001/library/mariadb:10.11`

**Cache & Queue:**
- `10.10.10.111:5001/library/redis:7-alpine`
- `10.10.10.111:5001/library/rabbitmq:3-management-alpine`

**RAG Services:**
- `10.10.10.111:5001/qdrant/qdrant:latest`
- `10.10.10.111:5001/mher/flower:2.0.1`
- `10.10.10.111:5001/jc21/nginx-proxy-manager:latest`

**Storage:**
- `10.10.10.111:5001/minio/minio:latest`
- `10.10.10.111:5001/minio/mc:latest`

**Monitoring (Docker Hub):**
- `10.10.10.111:5001/grafana/grafana:latest`
- `10.10.10.111:5001/grafana/loki:latest`
- `10.10.10.111:5001/grafana/promtail:latest`
- `10.10.10.111:5001/grafana/promtail:2.8.0`
- `10.10.10.111:5001/grafana/promtail:2.9.3`
- `10.10.10.111:5001/prom/prometheus:latest`
- `10.10.10.111:5001/prom/alertmanager:latest`
- `10.10.10.111:5001/prom/blackbox-exporter:latest`
- `10.10.10.111:5001/prom/node-exporter:latest`
- `10.10.10.111:5001/oliver006/redis_exporter:latest`
- `10.10.10.111:5001/oliver006/redis_exporter:v1.55.0`
- `10.10.10.111:5001/kbudde/rabbitmq-exporter:latest`
- `10.10.10.111:5001/zcube/cadvisor:latest`

**Cache Server Infrastructure:**
- `10.10.10.111:5001/library/registry:2`
- `10.10.10.111:5001/verdaccio/verdaccio:5`
- `10.10.10.111:5001/library/nginx:alpine`
- `10.10.10.111:5001/muccg/devpi:latest`
- `10.10.10.111:5001/sameersbn/apt-cacher-ng:3.7.4-20220421`

### quay.io (پورت 5003)

**Monitoring:**
- `10.10.10.111:5003/prometheus/node-exporter:latest`
- `10.10.10.111:5003/prometheus/node-exporter:v1.7.0`
- `10.10.10.111:5003/prometheuscommunity/postgres-exporter:latest`
- `10.10.10.111:5003/prometheuscommunity/postgres-exporter:v0.15.0`
- `10.10.10.111:5003/oliver006/redis_exporter:v1.55.0`

### ghcr.io (پورت 5002)
- آماده برای استفاده — images را با `10.10.10.111:5002/org/image:tag` دریافت کنید

### gcr.io (پورت 5004)
- آماده برای استفاده — images را با `10.10.10.111:5004/project/image:tag` دریافت کنید
- **نکته:** `gcr.io/cadvisor` بلاک است — از `zcube/cadvisor` استفاده کنید

### registry.k8s.io (پورت 5005)
- آماده برای استفاده — images را با `10.10.10.111:5005/image:tag` دریافت کنید

---

## 🐍 Python Packages

### روش الف: از devpi (پورت 3141) — برای packages معمولی

**استفاده:**
```bash
pip install <package> \
  --index-url http://10.10.10.111:3141/root/pypi/+simple/ \
  --trusted-host 10.10.10.111
```

**Packages کش شده در devpi:**

**RAG-Ingest:**
- Django==5.0.8, djangorestframework==3.14.0, django-filter==23.3
- django-simple-history==3.4.0, django-mptt==0.15.0, whitenoise==6.5.0
- psycopg[binary]==3.1.19, pgvector==0.2.5
- celery==5.3.4, django-celery-beat==2.6.0
- redis==5.0.7, django-redis==5.4.0
- gunicorn==21.2.0, python-dotenv==1.0.0
- Pillow==10.4.0, requests==2.31.0
- boto3==1.34.162, botocore==1.34.162, django-storages==1.14.2
- jdatetime>=4.1.1, django-cors-headers==4.3.1
- prometheus-client==0.20.0
- transformers>=4.30.0, sentence-transformers>=2.3.1
- huggingface_hub>=0.23.0, hazm>=0.7.0
- python-docx>=1.0.0, beautifulsoup4>=4.12.0
- scikit-learn>=1.3.0, scipy>=1.11.0, numpy>=1.24.0
- PyPDF2>=3.0.0, PyMuPDF>=1.24.0
- prometheus-fastapi-instrumentator>=6.1.0
- torch>=2.0.0

**RAG-Reranker:**
- fastapi==0.109.0, uvicorn[standard]==0.27.0
- sentence-transformers>=2.3.1, pydantic==2.5.3

**RAG-Users:**
- Django==4.2.7, djangorestframework-simplejwt==5.3.0
- drf-nested-routers==0.93.4, django-filter==23.5
- drf-yasg==1.21.7, psycopg2-binary==2.9.9
- redis==5.0.1, python-decouple==3.8
- drf-spectacular==0.26.5, boto3==1.29.7
- channels==4.0.0, channels-redis==4.1.0, daphne==4.0.0
- aiohttp==3.9.1, cryptography==41.0.7
- pyotp==2.9.0, qrcode==7.4.2
- django-otp==1.3.0, django-two-factor-auth==1.15.5
- django-allauth==0.57.0, httpx==0.25.1
- python-jose==3.3.0, stripe==7.4.0
- reportlab==4.0.7, weasyprint==60.1
- jdatetime==4.1.1, python-dateutil==2.8.2
- openpyxl==3.1.2, django-admin-rangefilter==0.11.2
- django-import-export==3.3.3, django-extensions==3.2.3
- django-debug-toolbar==4.2.0, uvicorn==0.22.0
- sentry-sdk==1.38.0, prometheus-client==0.19.0
- django-prometheus==2.3.1, user-agents==2.2.0
- django-jazzmin==2.6.0

**Common:**
- Pillow>=10.0.0, flower>=2.0.0, jdatetime>=4.1.0
- numpy>=1.24.3, pandas>=2.0.0, qdrant-client>=1.7.0
- pip, wheel, setuptools

### روش ب: Offline Packages (Nginx Static) — برای packages بزرگ

**URL:** `http://10.10.10.111/pypi-offline/`

**Packages موجود:**
- `sentence-transformers==5.2.3` + همه dependencies (66 packages، ~4GB)
  - شامل: torch==2.10.0, transformers==5.2.0, numpy, scipy, scikit-learn, Pillow, nltk و CUDA packages
- `sentence-transformers==2.3.1` + همه dependencies (نسخه قدیمی، برای سازگاری)

**نحوه استفاده:**
```bash
# دانلود
mkdir -p ~/offline-packages
wget -r -np -nH --cut-dirs=1 -R "index.html*" http://10.10.10.111/pypi-offline/

# نصب نسخه جدید
pip install sentence-transformers==5.2.3 \
  --no-index \
  --find-links ~/offline-packages/pypi-offline/

# یا نسخه قدیمی
pip install sentence-transformers==2.3.1 \
  --no-index \
  --find-links ~/offline-packages/pypi-offline/
```

**افزودن package جدید به offline:**
```bash
# روی سرور کش:
sudo bash /srv/deployment/cache-manager.sh add-offline "torch>=2.0.0 tensorflow>=2.13.0"
```

---

## 🤖 HuggingFace Models (Offline)

**URL:** `http://10.10.10.111/models/`

**مدل‌های موجود:**
- `intfloat-multilingual-e5-large` (~2.2GB) — Multilingual embedding model (ONNX format)

### نحوه دانلود و استفاده

**مرحله 1: دانلود مدل از سرور کش**
```bash
# روش الف: با rsync (توصیه می‌شود)
mkdir -p ~/models
rsync -avz --progress 10.10.10.111:/srv/data/huggingface-models/intfloat-multilingual-e5-large/ \
    ~/models/intfloat-multilingual-e5-large/

# روش ب: با wget
mkdir -p ~/models
wget -r -np -nH --cut-dirs=2 -R "index.html*" \
    http://10.10.10.111/models/intfloat-multilingual-e5-large/ \
    -P ~/models/
```

**مرحله 2: استفاده در کد Python**
```python
from sentence_transformers import SentenceTransformer

# بارگذاری از مسیر local
model = SentenceTransformer('~/models/intfloat-multilingual-e5-large')

# استفاده
embeddings = model.encode(["سلام", "Hello", "مرحبا"])
```

**در Dockerfile:**
```dockerfile
FROM 10.10.10.111:5001/library/python:3.11-slim

# کپی مدل به container
COPY models/intfloat-multilingual-e5-large /app/models/intfloat-multilingual-e5-large

# استفاده
RUN pip install sentence-transformers
ENV TRANSFORMERS_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1
```

### افزودن مدل جدید

**روی سرور کش (10.10.10.111):**
```bash
# دانلود مدل با Docker
sudo docker run --rm -v /srv/data/huggingface-models:/models python:3.11-slim bash -c "
pip install -q huggingface_hub
python3 -c \"
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='<model-name>',
    cache_dir='/models/.cache',
    local_dir='/models/<model-dir-name>',
    local_dir_use_symlinks=False
)
\"
"

# مثال:
# intfloat/multilingual-e5-large → /models/intfloat-multilingual-e5-large
# sentence-transformers/paraphrase-multilingual-mpnet-base-v2 → /models/paraphrase-multilingual-mpnet-base-v2
```

**نکات:**
- مدل‌ها در `/srv/data/huggingface-models/` ذخیره می‌شوند
- از طریق Nginx در `http://10.10.10.111/models/` سرو می‌شوند
- نام دایرکتوری: `/` در نام مدل را با `-` جایگزین کنید

---

## 📦 npm Packages (پورت 4873)

**استفاده:**
```bash
npm config set registry http://10.10.10.111:4873
npm install <package>
```

**رفتار:** Pull-through cache — اگر package در کش نباشد، خودکار از npmjs.org دریافت و کش می‌شود.

---

## 📦 apt Packages (پورت 3142)

**پیکربندی:**
```bash
echo 'Acquire::http::Proxy "http://10.10.10.111:3142";' | sudo tee /etc/apt/apt.conf.d/00proxy
```

**Packages کش شده:**
- Ubuntu 24.04 base system + dist-upgrade
- Docker CE + containerd + docker-compose-plugin
- Build tools: gcc, g++, make, cmake, pkg-config
- Python: python3, python3-pip, python3-venv, python3-dev
- PostgreSQL: postgresql-client, libpq-dev
- System utilities: htop, vim, nano, curl, wget, jq, rsync

**رفتار:** Pull-through cache — packages جدید خودکار کش می‌شوند.

---

## 🏔️ Alpine Linux Packages (پورت 3143)

**پیکربندی:**
```dockerfile
RUN echo "http://10.10.10.111:3143/alpine/v3.19/main" > /etc/apk/repositories && \
    echo "http://10.10.10.111:3143/alpine/v3.19/community" >> /etc/apk/repositories
```

**Packages کش شده:**
- Alpine v3.19 base + common packages
- Build tools, Python, PostgreSQL client, system utilities

---

## 🔑 GPG Keys & Status (پورت 80)

**موارد موجود:**
- Docker GPG key: `http://10.10.10.111/keys/docker.gpg`
- Server status: `http://10.10.10.111/`
- Offline packages: `http://10.10.10.111/pypi-offline/`

---

## 🔄 بروزرسانی خودکار

**سرور کش هر جمعه ساعت 21:00 UTC:**
1. تمام Docker images را re-pull می‌کند (آپدیت :latest tags)
2. تمام Python packages را upgrade می‌کند
3. apt packages جدید Ubuntu را کش می‌کند

**برای افزودن موارد جدید:**
```bash
# روی سرور کش:
sudo bash /srv/deployment/cache-manager.sh
# گزینه 2: افزودن Docker image
# گزینه 3: افزودن Python package (devpi)
# گزینه 4: افزودن Python package بزرگ (offline)
```

---

## 📞 پشتیبانی

اگر image یا package مورد نیاز شما در کش نبود:

1. **فوری:** به سرور کش SSH کنید و اضافه کنید
2. **دائمی:** به تیم cache اطلاع دهید تا به لیست warm-up اضافه شود

**تماس با مدیر سرور کش:** `ahad@10.10.10.111`

---

# 🔄 استراتژی بروزرسانی سیستم عامل

## هدف

سرور کش باید خودش را بروز نگه دارد تا بتواند آپدیت‌های سیستم عامل را به سرورهای client ارائه دهد.

---

## استراتژی بروزرسانی سرور کش (10.10.10.111)

سرور کش **مستقیماً** به اینترنت متصل است و از apt-cacher-ng خودش استفاده **نمی‌کند**.

### گزینه 1: Unattended Upgrades (توصیه شده)

```bash
# نصب
sudo apt-get install -y unattended-upgrades apt-listchanges

# پیکربندی: /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}:${distro_codename}-updates";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";

# فعال‌سازی: /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
```

**مزایا:**
- ✅ بروزرسانی امن و تست شده
- ✅ فقط security updates نصب می‌شود (یا همه updates)
- ✅ لاگ کامل
- ✅ می‌تواند خودکار restart کند (اختیاری)

### گزینه 2: Cron Job برای بروزرسانی هفتگی

```bash
# /etc/cron.d/cache-server-update
# هر جمعه ساعت 20:00 UTC (یک ساعت قبل از warm-up)
0 20 * * 5 root apt-get update && apt-get dist-upgrade -y && apt-get autoremove -y && apt-get autoclean >> /var/log/cache-server-update.log 2>&1
```

---

## کش کردن آپدیت‌ها برای Client Servers

بعد از اینکه سرور کش خودش را آپدیت کرد، packages جدید در apt-cacher-ng کش می‌شوند.

**مکانیزم:**
1. سرور کش `apt-get update && apt-get dist-upgrade` را اجرا می‌کند
2. apt-cacher-ng packages جدید را از Ubuntu mirrors دانلود و کش می‌کند
3. Client servers می‌توانند همین packages را از cache دریافت کنند

---

## Cron پیشنهادی برای سرور کش

```bash
# /etc/cron.d/rag-cache-warmup
# System updates (download only, no install)
0 20 * * 5 root apt-get update && apt-get dist-upgrade --download-only -y >> /var/log/cache-warmup-apt.log 2>&1

# Docker images
0 21 * * 5 root bash /srv/deployment/cache-manager.sh warmup-images >> /var/log/cache-warmup-images.log 2>&1

# Python packages
30 21 * * 5 root bash /srv/deployment/cache-manager.sh warmup-pypi >> /var/log/cache-warmup-pypi.log 2>&1
```

---

## بررسی وضعیت

```bash
# آخرین آپدیت سرور کش
ls -lh /var/lib/apt/lists/ | head

# packages در apt-cacher-ng
du -sh /srv/data/apt-cacher-ng/

# لاگ unattended-upgrades
tail -f /var/log/unattended-upgrades/unattended-upgrades.log
```

---

## نکات مهم

1. **Kernel updates:** اگر kernel آپدیت شد، سرور کش نیاز به restart دارد
2. **Docker updates:** اگر Docker آپدیت شد، باید `systemctl restart docker` اجرا شود
3. **Testing:** قبل از اعمال در production، در محیط test آزمایش کنید
4. **Monitoring:** لاگ‌ها را بررسی کنید تا مطمئن شوید آپدیت‌ها موفق بوده‌اند

---

## چک‌لیست نصب

- [ ] نصب `unattended-upgrades`
- [ ] پیکربندی `/etc/apt/apt.conf.d/50unattended-upgrades`
- [ ] فعال‌سازی `/etc/apt/apt.conf.d/20auto-upgrades`
- [ ] اضافه کردن cron برای `apt-get update` هفتگی
- [ ] تست: `sudo unattended-upgrade --dry-run`
- [ ] بررسی لاگ: `/var/log/unattended-upgrades/`
