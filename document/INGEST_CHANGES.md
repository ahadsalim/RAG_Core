# تغییرات مورد نیاز در سیستم Ingest

## 1. تغییرات در مدل‌ها

### اضافه کردن فیلد sync_status به Embedding
```python
# در فایل ingest/apps/embeddings/models.py

class Embedding(BaseModel):
    # فیلدهای موجود...
    
    # فیلدهای جدید برای sync
    synced_to_core = models.BooleanField(default=False, verbose_name='همگام شده با Core')
    synced_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان همگام‌سازی')
    sync_error = models.TextField(blank=True, verbose_name='خطای همگام‌سازی')
```

## 2. API Endpoints جدید

### اضافه کردن endpoint برای sync مستقیم
```python
# در فایل ingest/api/syncbridge/views.py

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_sync(request):
    """Trigger immediate sync to Core system."""
    sync_type = request.data.get('sync_type', 'incremental')
    
    if sync_type == 'full':
        # Sync تمام embeddings
        task = sync_all_embeddings_to_core.delay()
    else:
        # Sync تنها موارد جدید
        task = sync_new_embeddings_to_core.delay()
    
    return Response({
        'task_id': task.id,
        'status': 'initiated'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sync_status(request):
    """Get current sync status with Core."""
    pending_count = Embedding.objects.filter(synced_to_core=False).count()
    last_sync = SyncJob.objects.filter(
        job_type='embedding',
        status='success'
    ).order_by('-completed_at').first()
    
    return Response({
        'pending_embeddings': pending_count,
        'last_successful_sync': last_sync.completed_at if last_sync else None,
        'total_synced': Embedding.objects.filter(synced_to_core=True).count()
    })
```

## 3. Celery Tasks

### اضافه کردن task های sync
```python
# در فایل ingest/apps/embeddings/tasks.py

from celery import shared_task
import requests
from django.conf import settings

@shared_task
def sync_embeddings_batch(embedding_ids):
    """Sync a batch of embeddings to Core."""
    embeddings = Embedding.objects.filter(id__in=embedding_ids)
    
    # Prepare data for Core
    data = []
    for emb in embeddings:
        data.append({
            'id': str(emb.id),
            'vector': emb.vector,
            'text': emb.text_content,
            'document_id': str(emb.object_id),
            'metadata': {
                'content_type': emb.content_type.model,
                'created_at': emb.created_at.isoformat(),
                'model_id': emb.model_id,
                'dimension': emb.dim
            }
        })
    
    # Send to Core
    try:
        response = requests.post(
            f"{settings.CORE_API_URL}/sync/embeddings",
            json={'embeddings': data},
            headers={'Authorization': f'Bearer {settings.CORE_API_KEY}'}
        )
        response.raise_for_status()
        
        # Mark as synced
        embeddings.update(
            synced_to_core=True,
            synced_at=timezone.now(),
            sync_error=''
        )
        
        return {'status': 'success', 'count': len(data)}
        
    except Exception as e:
        embeddings.update(sync_error=str(e))
        return {'status': 'error', 'error': str(e)}

@shared_task
def sync_new_embeddings_to_core():
    """Sync all unsynced embeddings to Core."""
    unsynced = Embedding.objects.filter(synced_to_core=False)[:1000]
    
    if unsynced:
        embedding_ids = list(unsynced.values_list('id', flat=True))
        return sync_embeddings_batch.delay(embedding_ids)
    
    return {'status': 'nothing_to_sync'}
```

## 4. تنظیمات جدید

### اضافه کردن به settings
```python
# در فایل ingest/settings/base.py

# Core System Integration
CORE_API_URL = os.getenv('CORE_API_URL', 'http://localhost:7001/api/v1')
CORE_API_KEY = os.getenv('CORE_API_KEY', '')

# Sync Settings
SYNC_BATCH_SIZE = int(os.getenv('SYNC_BATCH_SIZE', '100'))
SYNC_INTERVAL_MINUTES = int(os.getenv('SYNC_INTERVAL_MINUTES', '5'))
```

## 5. دسترسی Read-Only برای Core

### ایجاد کاربر دیتابیس برای Core
```sql
-- در PostgreSQL
CREATE USER ingest_reader WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE ingest_db TO ingest_reader;
GRANT USAGE ON SCHEMA public TO ingest_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ingest_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ingest_reader;
```

## 6. Management Commands

### اضافه کردن command برای sync دستی
```python
# در فایل ingest/apps/embeddings/management/commands/sync_to_core.py

from django.core.management.base import BaseCommand
from ingest.apps.embeddings.tasks import sync_new_embeddings_to_core

class Command(BaseCommand):
    help = 'Manually sync embeddings to Core system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform full sync instead of incremental'
        )
    
    def handle(self, *args, **options):
        if options['full']:
            self.stdout.write('Starting full sync...')
            # Reset all sync flags
            Embedding.objects.update(synced_to_core=False)
        else:
            self.stdout.write('Starting incremental sync...')
        
        result = sync_new_embeddings_to_core()
        self.stdout.write(f'Sync completed: {result}')
```

## 7. Admin Interface

### اضافه کردن actions برای sync در admin
```python
# در فایل ingest/apps/embeddings/admin.py

@admin.action(description='Sync selected embeddings to Core')
def sync_to_core(modeladmin, request, queryset):
    ids = list(queryset.values_list('id', flat=True))
    task = sync_embeddings_batch.delay(ids)
    messages.success(request, f'Sync task started: {task.id}')

class EmbeddingAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_object', 'model_id', 'dim', 'synced_to_core', 'synced_at']
    list_filter = ['synced_to_core', 'model_id', 'dim']
    actions = [sync_to_core]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('content_type')
```

## 8. Monitoring

### اضافه کردن metrics برای sync
```python
# در فایل ingest/monitoring.py

from prometheus_client import Counter, Gauge, Histogram

# Metrics
sync_success_counter = Counter('ingest_sync_success_total', 'Total successful syncs to Core')
sync_error_counter = Counter('ingest_sync_error_total', 'Total failed syncs to Core')
pending_sync_gauge = Gauge('ingest_pending_sync_count', 'Number of items pending sync')
sync_duration_histogram = Histogram('ingest_sync_duration_seconds', 'Sync duration in seconds')
```

## 9. Environment Variables

### متغیرهای محیطی جدید
```bash
# در فایل .env

# Core Integration
CORE_API_URL=http://core-api:7001/api/v1
CORE_API_KEY=your-secure-api-key

# Database Read Access for Core
DATABASE_READER_USER=ingest_reader
DATABASE_READER_PASSWORD=secure_password

# Sync Configuration
AUTO_SYNC_ENABLED=true
SYNC_BATCH_SIZE=100
SYNC_INTERVAL_MINUTES=5
```

## 10. Docker Network

### اضافه کردن به docker-compose
```yaml
# در فایل deployment/docker-compose.yml

networks:
  ingest-network:
    driver: bridge
    name: ingest-network  # نام ثابت برای دسترسی از Core

services:
  postgres:
    networks:
      - ingest-network
    # سایر تنظیمات...

  django:
    networks:
      - ingest-network
    # سایر تنظیمات...
```

## نکات مهم

1. **Backward Compatibility**: تمام تغییرات باید backward compatible باشند
2. **Migration**: نیاز به ایجاد migration برای فیلدهای جدید
3. **Testing**: تست کامل sync قبل از production
4. **Monitoring**: پیگیری وضعیت sync در dashboard
5. **Rate Limiting**: محدودیت برای تعداد sync در دقیقه
6. **Error Handling**: مدیریت خطاها و retry logic
7. **Logging**: ثبت دقیق همه عملیات sync
