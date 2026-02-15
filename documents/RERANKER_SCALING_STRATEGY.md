# استراتژی Scaling برای Reranker Service

## 📊 وضعیت فعلی

### مشخصات Reranker
- **مدل:** BAAI/bge-reranker-v2-m3
- **حجم مدل:** ~1.5GB
- **حافظه مورد نیاز:** 2-4GB RAM
- **پردازنده:** CPU (فعلاً بدون GPU)
- **زمان پردازش:** ~500ms برای 20 chunk

### محدودیت‌های فعلی
- اجرا روی CPU (کند)
- Single instance (بدون load balancing)
- در همان ماشین Core API

---

## 🎯 گزینه‌های Scaling

### گزینه 1: ماشین مستقل اختصاصی (توصیه می‌شود ⭐)

#### مزایا
✅ **جداسازی کامل منابع:** Core API تحت تأثیر reranker نیست
✅ **GPU Support:** می‌توان GPU اختصاصی اضافه کرد (10x سریعتر)
✅ **Horizontal Scaling:** چند instance reranker با load balancer
✅ **Resource Optimization:** منابع متناسب با نیاز reranker
✅ **Kubernetes Ready:** آماده برای auto-scaling

#### معماری پیشنهادی
```
┌─────────────────────────────────────────────────────┐
│ Load Balancer (HAProxy/Nginx)                      │
│ http://reranker.internal:8100                      │
└──────────────┬──────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼─────┐   ┌──────▼─────┐
│ Reranker 1 │   │ Reranker 2 │
│ GPU/CPU    │   │ GPU/CPU    │
│ 4GB RAM    │   │ 4GB RAM    │
└────────────┘   └────────────┘
```

#### مشخصات ماشین پیشنهادی
- **CPU:** 4 cores (یا 1 GPU)
- **RAM:** 8GB
- **Storage:** 20GB SSD
- **Network:** 1Gbps internal
- **OS:** Ubuntu 22.04 LTS

#### هزینه تخمینی (ماهانه)
- **بدون GPU:** $30-50 (VPS معمولی)
- **با GPU:** $100-200 (GPU instance)

#### پیاده‌سازی با Docker Swarm
```yaml
# docker-compose.reranker.yml
version: '3.8'
services:
  reranker:
    image: your-registry/reranker:latest
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          memory: 2G
    networks:
      - internal
```

#### پیاده‌سازی با Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reranker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: reranker
  template:
    metadata:
      labels:
        app: reranker
    spec:
      containers:
      - name: reranker
        image: your-registry/reranker:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        ports:
        - containerPort: 8100
---
apiVersion: v1
kind: Service
metadata:
  name: reranker
spec:
  selector:
    app: reranker
  ports:
  - port: 8100
    targetPort: 8100
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: reranker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: reranker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

### گزینه 2: ارتقاء منابع ماشین فعلی

#### مزایا
✅ **ساده‌تر:** نیاز به تغییر معماری نیست
✅ **هزینه کمتر:** یک ماشین قوی‌تر به جای دو ماشین
✅ **Latency کمتر:** بدون network hop

#### معایب
❌ **Single Point of Failure:** اگر ماشین down شود، همه سرویس‌ها down می‌شوند
❌ **Resource Contention:** Core API و Reranker رقابت برای منابع
❌ **محدودیت Scaling:** نمی‌توان reranker را مستقل scale کرد
❌ **GPU Sharing:** اگر GPU اضافه شود، باید share شود

#### مشخصات ارتقاء
- **CPU:** 16 cores (فعلی: 8)
- **RAM:** 64GB (فعلی: 32GB)
- **GPU:** NVIDIA T4 یا بهتر (اختیاری)

#### هزینه تخمینی (ماهانه)
- **بدون GPU:** $100-150
- **با GPU:** $300-500

---

### گزینه 3: Hybrid (توصیه برای Production)

#### معماری
```
┌─────────────────────────────────────────────────────┐
│ Kubernetes Cluster                                  │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
│  │  Core API   │  │  Postgres   │  │   Redis     ││
│  │  (Node 1)   │  │  (Node 2)   │  │  (Node 2)   ││
│  └─────────────┘  └─────────────┘  └─────────────┘│
│                                                     │
│  ┌─────────────┐  ┌─────────────┐                 │
│  │ Reranker 1  │  │ Reranker 2  │                 │
│  │ GPU (Node 3)│  │ GPU (Node 4)│                 │
│  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────┘
```

#### مزایا
✅ **Auto-scaling:** Kubernetes HPA برای reranker
✅ **High Availability:** چند instance با load balancing
✅ **Resource Isolation:** هر سرویس در node مناسب خود
✅ **Cost Optimization:** scale down در زمان‌های کم‌بار

---

## 🚀 توصیه نهایی

### برای شروع (تا 1000 کاربر/روز)
**گزینه 1: یک ماشین مستقل برای Reranker**
- 4 CPU cores
- 8GB RAM
- بدون GPU (فعلاً)
- Docker Compose
- هزینه: ~$40/ماه

### برای رشد (1000-10000 کاربر/روز)
**گزینه 3: Kubernetes با 2 instance Reranker**
- هر instance: 2 CPU + 4GB RAM
- Auto-scaling بر اساس CPU/Memory
- Load balancer
- هزینه: ~$100/ماه

### برای مقیاس بزرگ (10000+ کاربر/روز)
**گزینه 3: Kubernetes با GPU**
- 2-4 instance با GPU (T4)
- Auto-scaling aggressive
- Monitoring و alerting
- هزینه: ~$400/ماه

---

## 📝 مراحل پیاده‌سازی گزینه 1 (ماشین مستقل)

### 1. تهیه ماشین جدید
```bash
# مشخصات
- Ubuntu 22.04 LTS
- 4 CPU cores
- 8GB RAM
- 20GB SSD
- IP: 10.10.10.60 (مثال)
```

### 2. نصب Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### 3. کپی فایل‌های Reranker
```bash
# روی ماشین جدید
mkdir -p /srv/reranker
cd /srv/reranker

# کپی فایل‌ها از ماشین فعلی
scp -r user@current-server:/srv/deployment/services/reranker/* .
```

### 4. ایجاد docker-compose.yml
```yaml
version: '3.8'
services:
  reranker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: reranker
    ports:
      - "8100:8100"
    environment:
      - RERANKER_MODEL=BAAI/bge-reranker-v2-m3
      - RERANKER_MODEL_PATH=/models/reranker
      - RERANKER_MAX_LENGTH=512
    volumes:
      - reranker-models:/models/reranker
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

volumes:
  reranker-models:
```

### 5. اجرا
```bash
docker compose up -d
```

### 6. بروزرسانی Core API
```bash
# در /srv/.env
RERANKER_SERVICE_URL="http://10.10.10.60:8100"
```

### 7. Restart Core API
```bash
cd /srv/deployment/docker
docker compose restart core-api
```

---

## 🔍 Monitoring و Metrics

### Health Check
```bash
curl http://10.10.10.60:8100/health
```

### Metrics پیشنهادی
- Request rate (req/sec)
- Average response time
- Memory usage
- CPU usage
- Error rate

### Prometheus + Grafana
```yaml
# اضافه کردن metrics endpoint به reranker
@app.get("/metrics")
async def metrics():
    return {
        "requests_total": request_counter,
        "avg_response_time_ms": avg_response_time,
        "memory_usage_mb": get_memory_usage()
    }
```

---

## ⚡ بهینه‌سازی با GPU

### تغییرات Dockerfile
```dockerfile
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Install Python
RUN apt-get update && apt-get install -y python3.11 python3-pip

# Install PyTorch with CUDA
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install sentence-transformers
RUN pip install sentence-transformers

# Rest of Dockerfile...
```

### تغییرات docker-compose.yml
```yaml
services:
  reranker:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### سرعت مورد انتظار
- **CPU:** ~500ms برای 20 chunks
- **GPU:** ~50ms برای 20 chunks (10x سریعتر)

---

## 💰 مقایسه هزینه

| گزینه | Setup | ماهانه | سرعت | HA | Auto-scale |
|-------|-------|--------|------|----|-----------| 
| ماشین فعلی | $0 | $0 | کند | ❌ | ❌ |
| ماشین مستقل CPU | $50 | $40 | متوسط | ❌ | ❌ |
| ماشین مستقل GPU | $100 | $150 | سریع | ❌ | ❌ |
| K8s 2 instances | $200 | $100 | متوسط | ✅ | ✅ |
| K8s GPU | $500 | $400 | خیلی سریع | ✅ | ✅ |

---

## 🎯 تصمیم‌گیری

### اگر بودجه محدود است
→ **ماشین مستقل CPU** ($40/ماه)

### اگر سرعت مهم است
→ **ماشین مستقل GPU** ($150/ماه)

### اگر reliability مهم است
→ **Kubernetes 2 instances** ($100/ماه)

### اگر همه چیز مهم است
→ **Kubernetes GPU** ($400/ماه)
