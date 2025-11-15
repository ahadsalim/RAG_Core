"""
Celery Application Configuration
Main Celery instance for async task processing
"""

from celery import Celery
from celery.schedules import crontab
from app.config.settings import settings

# Create Celery instance
celery_app = Celery(
    "core_tasks",
    broker=str(settings.celery_broker_url),
    backend=str(settings.celery_result_backend),
)

# Configure Celery
celery_app.conf.update(
    # Serialization
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    
    # Timezone
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    
    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Task routes
    task_routes={
        'app.tasks.sync.*': {'queue': 'sync'},
        'app.tasks.notifications.*': {'queue': 'notifications'},
        'app.tasks.cleanup.*': {'queue': 'cleanup'},
        'app.tasks.user.*': {'queue': 'user'},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Reset daily user limits at midnight
        'reset-daily-limits': {
            'task': 'app.tasks.user.reset_all_daily_limits',
            'schedule': crontab(hour=0, minute=0),  # Every day at midnight
        },
        # Cleanup old cache entries every 6 hours
        'cleanup-cache': {
            'task': 'app.tasks.cleanup.cleanup_old_cache',
            'schedule': crontab(hour='*/6', minute=0),  # Every 6 hours
        },
        # Cleanup old query cache every day
        'cleanup-query-cache': {
            'task': 'app.tasks.cleanup.cleanup_query_cache',
            'schedule': crontab(hour=2, minute=0),  # Every day at 2 AM
        },
        # Process sync queue every 5 minutes
        'process-sync-queue': {
            'task': 'app.tasks.sync.process_sync_queue',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
        # Send usage statistics to users system every hour
        'send-usage-stats': {
            'task': 'app.tasks.notifications.send_usage_statistics',
            'schedule': crontab(hour='*', minute=0),  # Every hour
        },
    },
)

# Auto-discover tasks from tasks module
celery_app.autodiscover_tasks(['app.tasks'])

# Task configuration
@celery_app.task(bind=True, max_retries=3)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
