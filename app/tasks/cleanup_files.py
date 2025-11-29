"""
Celery Tasks for File Cleanup
Periodic cleanup of expired temporary files
"""

from celery import shared_task
import structlog

from app.services.storage_service import get_storage_service

logger = structlog.get_logger()


@shared_task(name="cleanup_expired_temp_files")
def cleanup_expired_temp_files():
    """
    Cleanup expired temporary files from storage.
    
    This task should be run periodically (e.g., every hour) to remove
    files that have exceeded their expiration time.
    
    Returns:
        Number of files deleted
    """
    try:
        logger.info("Starting cleanup of expired temporary files")
        
        storage_service = get_storage_service()
        
        # Run cleanup synchronously (Celery task is already async)
        import asyncio
        deleted_count = asyncio.run(storage_service.cleanup_expired_files())
        
        logger.info(
            "Cleanup completed successfully",
            deleted_count=deleted_count
        )
        
        return {
            "status": "success",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
