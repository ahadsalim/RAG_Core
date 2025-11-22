"""
Synchronization API Endpoints
Endpoints for syncing data from Ingest system
"""

from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import structlog

from app.db.session import get_db
from app.core.dependencies import get_redis_client
from sqlalchemy import text, select, func
from app.models.user import UserProfile, Conversation, Message, QueryCache
from app.services.sync_service import SyncService
from app.services.qdrant_service import QdrantService
from app.config.settings import settings

logger = structlog.get_logger()
router = APIRouter()


# Request/Response Models
class EmbeddingData(BaseModel):
    """Embedding data model."""
    id: str = Field(..., description="Unique embedding ID", examples=["953652110735163"])
    vector: list[float] = Field(..., description="Embedding vector (dimension auto-detected: 768d, 1024d, 1536d, etc.)", examples=[[0.1, 0.2, 0.3]])
    text: str = Field(..., description="Original text content", examples=["ماده ۱۷۹ - شکار کردن موجب تملک است."])
    document_id: str = Field(..., description="Source document ID", examples=["dee1acff-8131-49ec-b7ed-78d543dcc539"])
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (language, jurisdiction, etc.)",
        examples=[{"language": "fa", "jurisdiction": "جمهوری اسلامی ایران"}]
    )


class SyncEmbeddingsRequest(BaseModel):
    """Sync embeddings request."""
    embeddings: list[EmbeddingData] = Field(
        ...,
        description="List of embeddings to sync",
        min_items=1,
        max_items=1000
    )
    sync_type: str = Field(
        default="incremental",
        description="Sync type: 'incremental' for updates, 'full' for complete replacement",
        pattern="^(incremental|full)$",
        examples=["incremental"]
    )


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    last_sync: Optional[str]
    pending_count: int
    synced_count: int
    error_count: int
    qdrant_status: Dict[str, Any]


# API key dependency (direct header validation to keep FastAPI/Pydantic happy)
async def verify_sync_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify API key for sync operations using X-API-Key header."""
    if x_api_key not in {settings.ingest_api_key, settings.users_api_key}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


# Sync embeddings endpoint
@router.post(
    "/embeddings",
    response_model=None,
    summary="Sync Embeddings from Ingest",
    description="""
    Receive and store embeddings from Ingest system into Qdrant vector database.
    
    **Authentication:** Requires X-API-Key header with INGEST_API_KEY.
    
    **Use Case:** Called by Ingest system when:
    - New documents are processed and embedded
    - Existing documents are updated
    - Batch sync operations are performed
    
    **Process:**
    1. Validates API key
    2. Receives embeddings with metadata
    3. Stores in Qdrant vector database (upsert operation)
    4. Returns sync statistics
    
    **Example Request:**
    ```bash
    curl -X POST https://core.domain.com/api/v1/sync/embeddings \
      -H "X-API-Key: your-ingest-api-key" \
      -H "Content-Type: application/json" \
      -d '{
        "embeddings": [
          {
            "id": "953652110735163",
            "vector": [0.1, 0.2, ...],
            "text": "ماده ۱۷۹ - شکار کردن موجب تملک است.",
            "document_id": "dee1acff-8131-49ec-b7ed-78d543dcc539",
            "metadata": {
              "language": "fa",
              "jurisdiction": "جمهوری اسلامی ایران"
            }
          }
        ],
        "sync_type": "incremental"
      }'
    ```
    """,
    responses={
        200: {
            "description": "Embeddings synced successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "synced_count": 1,
                        "timestamp": "2025-11-17T06:00:00Z"
                    }
                }
            }
        },
        401: {"description": "Invalid or missing API key"},
        500: {"description": "Sync operation failed"}
    }
)
async def sync_embeddings(
    request: SyncEmbeddingsRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_sync_api_key)
):
    """Receive embeddings from Ingest system for syncing to Qdrant."""
    try:
        sync_service = SyncService()
        
        # Process embeddings and determine vector field based on dimension
        embeddings_data = []
        vector_dims = set()
        
        for emb in request.embeddings:
            embeddings_data.append({
                "id": emb.id,
                "vector": emb.vector,
                "text": emb.text,
                "document_id": emb.document_id,
                "metadata": emb.metadata
            })
            vector_dims.add(len(emb.vector))
        
        # Auto-detect vector field based on dimension
        if len(vector_dims) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mixed vector dimensions in batch: {vector_dims}. All vectors must have the same dimension."
            )
        
        dim = vector_dims.pop()
        vector_field = sync_service._get_vector_field_by_dim(dim)
        
        logger.info(f"Auto-detected vector field: {vector_field} for dimension: {dim}")
        
        # Sync to Qdrant with auto-detected vector field
        synced_count = await sync_service.qdrant_service.upsert_embeddings(
            embeddings_data,
            vector_field=vector_field
        )
        
        logger.info(
            f"Synced {synced_count} embeddings",
            sync_type=request.sync_type
        )
        
        return {
            "status": "success",
            "synced_count": synced_count,
            "timestamp": datetime.utcnow().isoformat(),
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
    Uses Celery for async processing.
    """
    try:
        # Run sync via Celery
        from app.tasks.sync import trigger_full_sync_task
        task = trigger_full_sync_task.delay(batch_size=100)
        
        return {
            "status": "initiated",
            "message": "Full sync started in background",
            "task_id": task.id
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
    """Delete all embeddings for a specific document (async via Celery)."""
    try:
        # Run delete via Celery for better reliability
        from app.tasks.sync import delete_document_embeddings_task
        task = delete_document_embeddings_task.delay(document_id)
        
        return {
            "status": "initiated",
            "message": "Document deletion started",
            "document_id": document_id,
            "task_id": task.id
        }
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


# Retrieve full node information by point id
@router.get("/node/{point_id}")
async def get_node(
    point_id: str,
    api_key: str = Depends(verify_sync_api_key)
):
    """Return full information (vectors and metadata) for a specific node/point.
    Accepts external string ids and normalizes to Qdrant point id format.
    """
    try:
        # Rate limit to avoid data exfiltration via repeated node fetches
        await enforce_rate_limit("sync_node", api_key, limit=30, window_seconds=60)
        qdrant_service = QdrantService()
        record = await qdrant_service.get_point(point_id=point_id, with_vectors=True)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
        return {
            "status": "success",
            "node": record
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node: {str(e)}"
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


# Rate limiting using Redis (per API key)
async def enforce_rate_limit(prefix: str, api_key: str, limit: int, window_seconds: int):
    try:
        redis = await get_redis_client()
        key = f"rl:{prefix}:{api_key}"
        # Increment and set expiry on first hit
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        if current > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception as e:
        # On Redis failure, do not block but log
        logger.warning(f"Rate limit check failed: {e}")


# System statistics for managers
@router.get("/statistics")
async def get_system_statistics(
    api_key: str = Depends(verify_sync_api_key)
):
    """Return aggregated statistics of Core system for Ingest managers.
    Includes Qdrant stats, sync job stats, Redis and Core DB health and last sync time.
    Protected by API key and rate limited.
    """
    try:
        # Rate limit statistics queries to reasonable volume
        await enforce_rate_limit("sync_statistics", api_key, limit=120, window_seconds=60)

        # Base status via SyncService (qdrant info + ingest sync jobs + last_sync)
        sync_service = SyncService()
        base = await sync_service.get_sync_status()

        # Core DB health
        core_db = {"status": "unknown"}
        try:
            from app.db.session import get_session
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
            core_db = {"status": "healthy"}
        except Exception as e:
            core_db = {"status": "unhealthy", "error": str(e)}

        # Redis health
        redis_info = {"status": "unknown"}
        try:
            redis = await get_redis_client()
            await redis.ping()
            redis_info = {"status": "healthy"}
        except Exception as e:
            redis_info = {"status": "unhealthy", "error": str(e)}

        # PostgreSQL aggregate stats (available ones only)
        pg = {}
        try:
            from app.db.session import get_session
            async with get_session() as session:
                total_users = await session.scalar(select(func.count()).select_from(UserProfile))
                total_conversations = await session.scalar(select(func.count()).select_from(Conversation))
                total_messages = await session.scalar(select(func.count()).select_from(Message))
                total_tokens = await session.scalar(select(func.sum(UserProfile.total_tokens_used)).select_from(UserProfile))
                total_tokens = total_tokens or 0
                avg_processing_time = await session.scalar(
                    select(func.avg(Message.processing_time_ms)).select_from(Message).where(Message.processing_time_ms.is_not(None))
                )
                avg_processing_time = avg_processing_time or 0
                total_cache_hits = await session.scalar(select(func.sum(QueryCache.hit_count)).select_from(QueryCache))
                total_cache_hits = total_cache_hits or 0
                cache_entries = await session.scalar(select(func.count()).select_from(QueryCache))
                pg = {
                    "users": {"total": total_users},
                    "conversations": {"total": total_conversations},
                    "messages": {
                        "total": total_messages,
                        "total_tokens": total_tokens,
                        "avg_processing_time_ms": float(avg_processing_time) if avg_processing_time else 0.0,
                    },
                    "cache": {
                        "total_cache_hits": total_cache_hits,
                        "entries": cache_entries,
                    },
                }
        except Exception as e:
            logger.warning(f"PostgreSQL stats error: {e}")

        qdrant_info = base.get("qdrant", {})
        summary = {
            "total_users": pg.get("users", {}).get("total", 0),
            "total_conversations": pg.get("conversations", {}).get("total", 0),
            "total_messages": pg.get("messages", {}).get("total", 0),
            "total_vectors_in_qdrant": qdrant_info.get("points_count", 0),
        }

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "environment": settings.environment,
            "app_version": settings.app_version,
            "last_sync": base.get("last_sync"),
            "summary": summary,
            "postgresql": pg,
            "qdrant": {
                "total_points": qdrant_info.get("points_count", 0),
                "indexed_vectors": qdrant_info.get("vectors_count", 0),
                "status": qdrant_info.get("status", "unknown"),
                "collection_name": settings.qdrant_collection,
            },
            "sync_jobs": base.get("sync_jobs", {}),
            "core_db": core_db,
            "redis": redis_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system statistics: {str(e)}"
        )
