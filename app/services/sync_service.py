"""
Sync Service
Helper service for sync operations with Qdrant
"""

from typing import Dict, Any
from datetime import datetime
import structlog

from app.services.qdrant_service import QdrantService
from app.core.dependencies import get_redis_client

logger = structlog.get_logger()


class SyncService:
    """Service for syncing data to Qdrant via API."""
    
    def __init__(self):
        self.qdrant_service = QdrantService()
        
    
    def _get_vector_field_by_dim(self, dim: int) -> str:
        """Determine vector field name based on dimension."""
        if dim <= 512:
            return "small"
        elif dim <= 768:
            return "medium"
        elif dim <= 1024:
            return "large"  # e5-large, bge-m3
        elif dim <= 1536:
            return "xlarge"  # OpenAI ada-002, text-embedding-3-small
        else:
            return "default"  # 3072
    
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status and statistics."""
        try:
            redis = await get_redis_client()
            
            # Get last sync time
            last_sync = await redis.get("sync:last_embedding_sync")
            
            # Get Qdrant statistics
            qdrant_info = await self.qdrant_service.get_collection_info()
            
            return {
                "last_sync": last_sync,
                "qdrant": {
                    "vectors_count": qdrant_info.get("vectors_count", 0),
                    "points_count": qdrant_info.get("points_count", 0),
                    "status": qdrant_info.get("status", "unknown"),
                },
                "sync_jobs": {
                    "total_24h": 0,
                    "pending": 0,
                    "running": 0,
                    "success": 0,
                    "error": 0,
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {
                "error": str(e),
                "last_sync": None,
                "qdrant": {},
                "sync_jobs": {}
            }
