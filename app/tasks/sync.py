"""
Sync Tasks
Async tasks for synchronization operations
"""

from typing import Dict, Any, Optional
from datetime import datetime
import structlog

from app.celery_app import celery_app
from app.services.sync_service import SyncService
from app.core.dependencies import get_redis_client

logger = structlog.get_logger()


@celery_app.task(
    name="app.tasks.sync.sync_embeddings_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def sync_embeddings_task(
    self,
    batch_size: int = 100,
    since: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sync embeddings from Ingest pgvector to Qdrant.
    
    Args:
        batch_size: Number of embeddings per batch
        since: ISO format datetime to sync from
        
    Returns:
        Sync statistics
    """
    try:
        import asyncio
        
        sync_service = SyncService()
        since_dt = datetime.fromisoformat(since) if since else None
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sync_service.sync_embeddings_from_pgvector(
                batch_size=batch_size,
                since=since_dt
            )
        )
        
        logger.info(
            "Embedding sync task completed",
            task_id=self.request.id,
            **result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Sync task failed: {e}", task_id=self.request.id)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 60)


@celery_app.task(
    name="app.tasks.sync.process_sync_queue",
    bind=True,
    max_retries=3
)
def process_sync_queue(self) -> Dict[str, Any]:
    """
    Process pending items from sync queue.
    Runs periodically via Celery Beat.
    
    Returns:
        Processing statistics
    """
    try:
        import asyncio
        
        sync_service = SyncService()
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sync_service.sync_from_sync_queue()
        )
        
        if result.get("total_processed", 0) > 0:
            logger.info(
                "Sync queue processed",
                task_id=self.request.id,
                **result
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Sync queue task failed: {e}", task_id=self.request.id)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@celery_app.task(
    name="app.tasks.sync.trigger_full_sync_task",
    bind=True,
    max_retries=1,
    time_limit=3600  # 1 hour limit
)
def trigger_full_sync_task(self, batch_size: int = 100) -> Dict[str, Any]:
    """
    Trigger full synchronization from Ingest to Qdrant.
    This is a heavy operation.
    
    Args:
        batch_size: Number of embeddings per batch
        
    Returns:
        Sync statistics
    """
    try:
        import asyncio
        
        logger.info("Starting full sync", task_id=self.request.id)
        
        sync_service = SyncService()
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sync_service.sync_embeddings_from_pgvector(
                batch_size=batch_size
            )
        )
        
        logger.info(
            "Full sync completed",
            task_id=self.request.id,
            **result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Full sync task failed: {e}", task_id=self.request.id)
        # Don't retry full sync automatically
        return {"error": str(e), "status": "failed"}


@celery_app.task(
    name="app.tasks.sync.delete_document_embeddings_task",
    bind=True,
    max_retries=3
)
def delete_document_embeddings_task(
    self,
    document_id: str
) -> Dict[str, Any]:
    """
    Delete all embeddings for a specific document.
    
    Args:
        document_id: Document UUID
        
    Returns:
        Deletion result
    """
    try:
        import asyncio
        
        sync_service = SyncService()
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        deleted = loop.run_until_complete(
            sync_service.qdrant_service.delete_by_document_id(document_id)
        )
        
        logger.info(
            f"Deleted embeddings for document {document_id}",
            task_id=self.request.id,
            deleted=deleted
        )
        
        return {
            "status": "success",
            "document_id": document_id,
            "deleted": deleted
        }
        
    except Exception as e:
        logger.error(
            f"Delete embeddings task failed: {e}",
            task_id=self.request.id,
            document_id=document_id
        )
        raise self.retry(exc=e, countdown=60)
