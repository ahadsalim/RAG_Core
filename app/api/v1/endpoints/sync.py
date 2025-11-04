"""
Synchronization API Endpoints
Endpoints for syncing data from Ingest system
"""

from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import structlog

from app.db.session import get_db
from app.services.sync_service import SyncService
from app.core.security import verify_api_key
from app.config.settings import settings

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class EmbeddingData(BaseModel):
    """Embedding data model."""
    id: str
    vector: list[float]
    text: str
    document_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SyncEmbeddingsRequest(BaseModel):
    """Sync embeddings request."""
    embeddings: list[EmbeddingData]
    sync_type: str = Field(default="incremental")  # incremental, full


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    last_sync: Optional[str]
    pending_count: int
    synced_count: int
    error_count: int
    qdrant_status: Dict[str, Any]


class SyncStatisticsResponse(BaseModel):
    """Complete sync statistics response."""
    timestamp: str
    ingest_database: Dict[str, Any]
    core_qdrant: Dict[str, Any]
    sync_progress: Dict[str, Any]
    summary: Dict[str, Any]


# API key dependency
async def verify_sync_api_key(api_key: str = Depends(verify_api_key)):
    """Verify API key for sync operations."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    return api_key


# Sync embeddings endpoint
@router.post("/embeddings")
async def sync_embeddings(
    request: SyncEmbeddingsRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_sync_api_key)
):
    """
    Receive embeddings from Ingest system for syncing to Qdrant.
    
    This endpoint is called by the Ingest system to push embeddings.
    """
    try:
        sync_service = SyncService()
        
        # Process embeddings
        embeddings_data = []
        for emb in request.embeddings:
            embeddings_data.append({
                "id": emb.id,
                "vector": emb.vector,
                "text": emb.text,
                "document_id": emb.document_id,
                "metadata": emb.metadata
            })
        
        # Sync to Qdrant (using "medium" vector field for 768-dim embeddings)
        synced_count = await sync_service.qdrant_service.upsert_embeddings(
            embeddings_data,
            vector_field="medium"  # For multilingual-e5-base (768 dim)
        )
        
        logger.info(
            f"Synced {synced_count} embeddings",
            sync_type=request.sync_type
        )
        
        return {
            "status": "success",
            "synced_count": synced_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


# Trigger full sync
@router.post("/trigger-full-sync")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_sync_api_key)
):
    """
    Trigger a full synchronization from Ingest pgvector to Qdrant.
    
    This is a heavy operation and should be run carefully.
    """
    try:
        # Run sync in background
        background_tasks.add_task(run_full_sync)
        
        return {
            "status": "initiated",
            "message": "Full sync started in background"
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}"
        )


# Get sync status
@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    api_key: str = Depends(verify_sync_api_key)
):
    """Get current synchronization status."""
    try:
        sync_service = SyncService()
        status = await sync_service.get_sync_status()
        
        return SyncStatusResponse(
            last_sync=status.get("last_sync"),
            pending_count=status.get("sync_jobs", {}).get("pending", 0),
            synced_count=status.get("qdrant", {}).get("points_count", 0),
            error_count=status.get("sync_jobs", {}).get("error", 0),
            qdrant_status=status.get("qdrant", {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


# Process sync queue
@router.post("/process-queue")
async def process_sync_queue(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_sync_api_key)
):
    """
    Process pending items from sync queue.
    
    This reads from the Ingest sync queue table and processes pending jobs.
    """
    try:
        sync_service = SyncService()
        result = await sync_service.sync_from_sync_queue()
        
        return {
            "status": "success",
            "processed": result.get("total_processed", 0),
            "success": result.get("total_success", 0),
            "errors": result.get("total_errors", 0),
            "duration": result.get("duration", 0)
        }
        
    except Exception as e:
        logger.error(f"Queue processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Queue processing failed: {str(e)}"
        )


# Delete document embeddings
@router.delete("/document/{document_id}")
async def delete_document_embeddings(
    document_id: str,
    api_key: str = Depends(verify_sync_api_key)
):
    """Delete all embeddings for a specific document."""
    try:
        sync_service = SyncService()
        deleted = await sync_service.qdrant_service.delete_by_document_id(
            document_id
        )
        
        return {
            "status": "success",
            "document_id": document_id,
            "deleted": deleted
        }
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


# Get complete statistics
@router.get("/statistics", response_model=SyncStatisticsResponse)
async def get_sync_statistics(
    api_key: str = Depends(verify_sync_api_key)
):
    """
    Get complete synchronization statistics.
    
    Returns detailed statistics from both Ingest database and Core Qdrant,
    including sync progress and transfer status.
    """
    try:
        sync_service = SyncService()
        stats = await sync_service.get_complete_statistics()
        
        return SyncStatisticsResponse(
            timestamp=stats["timestamp"],
            ingest_database=stats["ingest_database"],
            core_qdrant=stats["core_qdrant"],
            sync_progress=stats["sync_progress"],
            summary=stats["summary"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


# Helper functions
async def run_full_sync():
    """Run full synchronization in background."""
    try:
        sync_service = SyncService()
        result = await sync_service.sync_embeddings_from_pgvector(
            batch_size=100
        )
        
        logger.info(
            "Full sync completed",
            total_processed=result.get("total_processed"),
            total_synced=result.get("total_synced"),
            duration=result.get("duration")
        )
        
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
