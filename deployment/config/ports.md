# Port Configuration - Core System

## پورت‌های استفاده شده در سیستم Core

| Service | Port | Description |
|---------|------|-------------|
| Core API | 7001 | FastAPI Application |
| PostgreSQL Core | 7433 | Database (changed from 5432 to avoid conflict) |
| Redis Core | 7379 | Cache & Queue (changed from 6379 to avoid conflict) |
| Qdrant | 7333 | Vector Database HTTP |
| Qdrant GRPC | 7334 | Vector Database GRPC |
| Flower | 7555 | Celery Monitoring |

## پورت‌های سیستم Ingest (برای اجتناب از تداخل)

| Service | Port |
|---------|------|
| Ingest API | 8000 |
| PostgreSQL Ingest | 5432 |
| Redis Ingest | 6379 |
| Elasticsearch | 9200 |

## یادداشت
تمام پورت‌ها طوری انتخاب شده‌اند که با سیستم Ingest تداخل نداشته باشند و می‌توانند روی یک سرور اجرا شوند.
