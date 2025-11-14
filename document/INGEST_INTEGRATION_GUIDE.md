# راهنمای یکپارچه‌سازی سیستم Ingest با Core

## مرحله 1: ایجاد کاربر Read-Only در PostgreSQL

در سرور Ingest، به دیتابیس PostgreSQL متصل شوید و دستورات زیر را اجرا کنید:

```sql
-- اتصال به دیتابیس ingest
\c ingest_db;

-- ایجاد کاربر read-only برای Core
CREATE USER ingest_reader WITH PASSWORD 'secure_reader_password';
GRANT CONNECT ON DATABASE ingest_db TO ingest_reader;
GRANT USAGE ON SCHEMA public TO ingest_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ingest_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ingest_reader;
```

## مرحله 2: اضافه کردن API Endpoint در Ingest

### فایل جدید: `ingest/api/core_sync.py`

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
import requests
from django.conf import settings
from ingest.apps.embeddings.models import Embedding

@csrf_exempt
@require_POST
def trigger_sync_to_core(request):
    """Trigger sync of embeddings to Core system."""
    try:
        # Get unsynced embeddings
        embeddings = Embedding.objects.filter(synced_to_core=False)[:100]
        
        # Prepare data for Core
        data = []
        for emb in embeddings:
            data.append({
                'id': str(emb.id),
                'vector': emb.vector.tolist() if hasattr(emb.vector, 'tolist') else emb.vector,
                'text': emb.text_content,
                'document_id': str(emb.object_id),
                'metadata': {
                    'content_type': emb.content_type.model,
                    'model_id': emb.model_id,
                    'created_at': emb.created_at.isoformat()
                }
            })
        
        # Send to Core API
        response = requests.post(
            f"{settings.CORE_API_URL}/api/v1/sync/embeddings",
            json={'embeddings': data},
            headers={'X-API-Key': settings.CORE_API_KEY}
        )
        
        if response.status_code == 200:
            # Mark as synced
            embeddings.update(synced_to_core=True)
            return JsonResponse({'status': 'success', 'synced': len(data)})
        else:
            return JsonResponse({'status': 'error', 'message': response.text}, status=500)
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_sync_status(request):
    """Get sync status with Core."""
    unsynced = Embedding.objects.filter(synced_to_core=False).count()
    synced = Embedding.objects.filter(synced_to_core=True).count()
    
    return JsonResponse({
        'unsynced': unsynced,
        'synced': synced,
        'total': unsynced + synced
    })
```

## مرحله 3: اضافه کردن فیلد sync به مدل

### ویرایش فایل: `ingest/apps/embeddings/models.py`

```python
class Embedding(models.Model):
    # فیلدهای موجود...
    
    # فیلدهای جدید
    synced_to_core = models.BooleanField(
        default=False,
        verbose_name='همگام شده با Core',
        db_index=True
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان همگام‌سازی'
    )
```

سپس migration ایجاد کنید:
```bash
python manage.py makemigrations embeddings
python manage.py migrate embeddings
```

## مرحله 4: اضافه کردن به URLs

### ویرایش فایل: `ingest/urls.py`

```python
from ingest.api import core_sync

urlpatterns = [
    # سایر URLs...
    path('api/core/sync/', core_sync.trigger_sync_to_core, name='core_sync'),
    path('api/core/sync-status/', core_sync.get_sync_status, name='core_sync_status'),
]
```

## مرحله 5: متغیرهای محیطی

### اضافه کردن به `.env`:

```bash
# Core System Integration
CORE_API_URL=http://localhost:7001
CORE_API_KEY=your-secure-api-key-here

# Database Read Access for Core
INGEST_DB_READER_HOST=localhost
INGEST_DB_READER_PORT=5432
INGEST_DB_READER_NAME=ingest_db
INGEST_DB_READER_USER=ingest_reader
INGEST_DB_READER_PASSWORD=secure_reader_password
```

## مرحله 6: Celery Task برای Sync خودکار

### فایل جدید: `ingest/tasks/core_sync.py`

```python
from celery import shared_task
from django.conf import settings
import requests
from ingest.apps.embeddings.models import Embedding

@shared_task
def auto_sync_to_core():
    """Automatically sync new embeddings to Core every 5 minutes."""
    embeddings = Embedding.objects.filter(synced_to_core=False)[:100]
    
    if not embeddings:
        return {'status': 'nothing_to_sync'}
    
    data = []
    for emb in embeddings:
        data.append({
            'id': str(emb.id),
            'vector': emb.vector.tolist() if hasattr(emb.vector, 'tolist') else emb.vector,
            'text': emb.text_content,
            'document_id': str(emb.object_id),
            'metadata': {
                'content_type': emb.content_type.model,
                'model_id': emb.model_id,
            }
        })
    
    try:
        response = requests.post(
            f"{settings.CORE_API_URL}/api/v1/sync/embeddings",
            json={'embeddings': data},
            headers={'X-API-Key': settings.CORE_API_KEY},
            timeout=30
        )
        
        if response.status_code == 200:
            embeddings.update(synced_to_core=True)
            return {'status': 'success', 'synced': len(data)}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

### اضافه کردن به Celery Beat Schedule:

```python
# در settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # سایر tasks...
    'sync-to-core': {
        'task': 'ingest.tasks.core_sync.auto_sync_to_core',
        'schedule': crontab(minute='*/5'),  # هر 5 دقیقه
    },
}
```

## مرحله 7: Docker Network مشترک

### ویرایش `ingest/deployment/docker-compose.yml`:

```yaml
networks:
  ingest-network:
    driver: bridge
    name: shared-network  # نام مشترک برای هر دو سیستم
  
services:
  postgres:
    networks:
      - ingest-network
    # سایر تنظیمات...
```

## مرحله 8: اسکریپت تست ارتباط

### فایل جدید: `test_core_connection.py`

```python
#!/usr/bin/env python
"""Test connection between Ingest and Core systems."""

import os
import sys
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def test_core_api():
    """Test Core API connection."""
    core_url = os.getenv('CORE_API_URL', 'http://localhost:7001')
    try:
        response = requests.get(f"{core_url}/health")
        if response.status_code == 200:
            print("✓ Core API is accessible")
            return True
    except Exception as e:
        print(f"✗ Core API connection failed: {e}")
    return False

def test_database_reader():
    """Test read-only database access."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('INGEST_DB_READER_HOST', 'localhost'),
            port=os.getenv('INGEST_DB_READER_PORT', '5432'),
            database=os.getenv('INGEST_DB_READER_NAME', 'ingest_db'),
            user=os.getenv('INGEST_DB_READER_USER', 'ingest_reader'),
            password=os.getenv('INGEST_DB_READER_PASSWORD', '')
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ingest_apps_embeddings_embedding")
        count = cursor.fetchone()[0]
        print(f"✓ Database reader access OK. Found {count} embeddings")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Database reader access failed: {e}")
    return False

def test_sync_endpoint():
    """Test sync endpoint."""
    core_url = os.getenv('CORE_API_URL', 'http://localhost:7001')
    api_key = os.getenv('CORE_API_KEY', '')
    
    try:
        response = requests.get(
            f"{core_url}/api/v1/sync/status",
            headers={'X-API-Key': api_key}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Sync endpoint accessible. Status: {data}")
            return True
    except Exception as e:
        print(f"✗ Sync endpoint failed: {e}")
    return False

if __name__ == "__main__":
    print("Testing Ingest-Core Integration...")
    print("-" * 40)
    
    results = [
        test_core_api(),
        test_database_reader(),
        test_sync_endpoint()
    ]
    
    if all(results):
        print("\n✓ All tests passed! Integration is ready.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Please check configuration.")
        sys.exit(1)
```

## چک‌لیست نهایی

- [ ] کاربر read-only در PostgreSQL ایجاد شده
- [ ] فیلدهای sync به مدل Embedding اضافه شده
- [ ] Migration اجرا شده
- [ ] API endpoints اضافه شده
- [ ] متغیرهای محیطی تنظیم شده
- [ ] Celery task برای sync خودکار پیکربندی شده
- [ ] Docker network مشترک تنظیم شده
- [ ] تست ارتباط انجام شده

## نکات امنیتی

1. **API Key**: حتماً یک API key قوی و یکتا تولید کنید
2. **Database Password**: رمز عبور قوی برای ingest_reader
3. **Network Isolation**: در production از شبکه‌های جداگانه استفاده کنید
4. **Rate Limiting**: برای sync endpoints محدودیت تعداد درخواست اعمال کنید
