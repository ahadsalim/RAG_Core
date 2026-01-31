"""
Sync Tasks
Async tasks for synchronization operations
"""

from typing import Dict, Any
import structlog

from app.celery_app import celery_app
from app.services.sync_service import SyncService

logger = structlog.get_logger()




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
