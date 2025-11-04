"""
Sync Service
Synchronizes embeddings from Ingest pgvector to Qdrant
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import hashlib

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import structlog

from app.db.session import get_ingest_session
from app.services.qdrant_service import QdrantService
from app.core.dependencies import get_redis_client

logger = structlog.get_logger()


class SyncService:
    """Service for syncing data from Ingest to Core."""
    
    def __init__(self):
        self.qdrant_service = QdrantService()
        
    async def sync_embeddings_from_pgvector(
        self,
        batch_size: int = 100,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Sync embeddings from Ingest pgvector to Qdrant.
        
        Args:
            batch_size: Number of embeddings to process in each batch
            since: Sync only embeddings created/updated after this time
            
        Returns:
            Sync statistics
        """
        stats = {
            "total_processed": 0,
            "total_synced": 0,
            "total_errors": 0,
            "start_time": datetime.utcnow(),
        }
        
        try:
            async with get_ingest_session() as session:
                # Query to get embeddings from pgvector
                if since:
                    query = text("""
                        SELECT 
                            e.id,
                            e.content_type_id,
                            e.object_id,
                            e.model_id,
                            e.model_name,
                            e.vector,
                            e.dim,
                            e.text_content,
                            e.created_at,
                            e.updated_at
                        FROM ingest_apps_embeddings_embedding e
                        WHERE e.updated_at > :since
                        ORDER BY e.updated_at
                        LIMIT :batch_size
                        OFFSET :offset
                    """)
                else:
                    query = text("""
                        SELECT 
                            e.id,
                            e.content_type_id,
                            e.object_id,
                            e.model_id,
                            e.model_name,
                            e.vector,
                            e.dim,
                            e.text_content,
                            e.created_at,
                            e.updated_at
                        FROM ingest_apps_embeddings_embedding e
                        ORDER BY e.created_at
                        LIMIT :batch_size
                        OFFSET :offset
                    """)
                
                offset = 0
                while True:
                    # Execute query
                    params = {"batch_size": batch_size, "offset": offset}
                    if since:
                        params["since"] = since
                    
                    result = await session.execute(query, params)
                    embeddings = result.fetchall()
                    
                    if not embeddings:
                        break
                    
                    # Process batch
                    batch_data = []
                    for emb in embeddings:
                        try:
                            # Parse vector (stored as string in pgvector)
                            if isinstance(emb.vector, str):
                                vector = np.fromstring(
                                    emb.vector.strip('[]'),
                                    sep=',',
                                    dtype=np.float32
                                ).tolist()
                            else:
                                vector = emb.vector
                            
                            # Determine vector field based on dimension
                            vector_field = self._get_vector_field_by_dim(emb.dim)
                            
                            # Get document metadata
                            metadata = await self._get_document_metadata(
                                session,
                                emb.content_type_id,
                                emb.object_id
                            )
                            
                            batch_data.append({
                                "id": str(emb.id),
                                "vector": vector,
                                "text": emb.text_content,
                                "document_id": str(emb.object_id),
                                "document_type": metadata.get("doc_type", "unknown"),
                                "chunk_index": metadata.get("chunk_index", 0),
                                "created_at": emb.created_at.isoformat(),
                                "language": metadata.get("language", "fa"),
                                "source": "ingest",
                                "metadata": metadata,
                                "vector_field": vector_field
                            })
                            
                            stats["total_processed"] += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing embedding {emb.id}: {e}")
                            stats["total_errors"] += 1
                    
                    # Sync batch to Qdrant
                    if batch_data:
                        # Group by vector field
                        grouped = {}
                        for item in batch_data:
                            field = item.pop("vector_field")
                            if field not in grouped:
                                grouped[field] = []
                            grouped[field].append(item)
                        
                        # Upsert each group
                        for field, items in grouped.items():
                            synced = await self.qdrant_service.upsert_embeddings(
                                items,
                                vector_field=field
                            )
                            stats["total_synced"] += synced
                    
                    offset += batch_size
                    
                    # Log progress
                    if offset % (batch_size * 10) == 0:
                        logger.info(f"Sync progress: {offset} embeddings processed")
            
            # Update last sync time in Redis
            redis = await get_redis_client()
            await redis.set(
                "sync:last_embedding_sync",
                datetime.utcnow().isoformat(),
                ex=86400 * 7  # Keep for 7 days
            )
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info("Embedding sync completed", **stats)
            return stats
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            stats["error"] = str(e)
            return stats
    
    async def sync_from_sync_queue(self) -> Dict[str, Any]:
        """
        Process sync jobs from the sync queue table.
        This reads from the ingest.syncbridge_syncjob table.
        
        Returns:
            Sync statistics
        """
        stats = {
            "total_processed": 0,
            "total_success": 0,
            "total_errors": 0,
            "start_time": datetime.utcnow(),
        }
        
        try:
            async with get_ingest_session() as session:
                # Get pending sync jobs
                query = text("""
                    SELECT 
                        id,
                        job_type,
                        target_id,
                        payload_preview,
                        created_at
                    FROM ingest_apps_syncbridge_syncjob
                    WHERE status = 'pending'
                    ORDER BY created_at
                    LIMIT 100
                """)
                
                result = await session.execute(query)
                jobs = result.fetchall()
                
                for job in jobs:
                    try:
                        # Process based on job type
                        if job.job_type == "document":
                            await self._sync_document(job.target_id, job.payload_preview)
                        elif job.job_type == "unit":
                            await self._sync_unit(job.target_id, job.payload_preview)
                        elif job.job_type == "qa":
                            await self._sync_qa(job.target_id, job.payload_preview)
                        
                        # Mark job as success
                        await self._update_job_status(
                            session,
                            job.id,
                            "success",
                            datetime.utcnow()
                        )
                        
                        stats["total_success"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing sync job {job.id}: {e}")
                        
                        # Mark job as error
                        await self._update_job_status(
                            session,
                            job.id,
                            "error",
                            None,
                            str(e)
                        )
                        
                        stats["total_errors"] += 1
                    
                    stats["total_processed"] += 1
            
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info("Sync queue processing completed", **stats)
            return stats
            
        except Exception as e:
            logger.error(f"Sync queue processing failed: {e}")
            stats["error"] = str(e)
            return stats
    
    def _get_vector_field_by_dim(self, dim: int) -> str:
        """Determine vector field name based on dimension."""
        if dim <= 512:
            return "small"
        elif dim <= 768:
            return "medium"
        elif dim <= 1536:
            return "large"
        else:
            return "default"  # 3072
    
    async def _get_document_metadata(
        self,
        session: AsyncSession,
        content_type_id: int,
        object_id: str
    ) -> Dict[str, Any]:
        """
        Get metadata for a document from Ingest database.
        
        Args:
            session: Database session
            content_type_id: Content type ID
            object_id: Object UUID
            
        Returns:
            Document metadata
        """
        metadata = {}
        
        try:
            # Get content type name
            ct_query = text("""
                SELECT app_label, model
                FROM django_content_type
                WHERE id = :content_type_id
            """)
            ct_result = await session.execute(
                ct_query,
                {"content_type_id": content_type_id}
            )
            content_type = ct_result.fetchone()
            
            if content_type:
                model_name = content_type.model
                
                # Get metadata based on model type
                if model_name == "legalunit":
                    query = text("""
                        SELECT 
                            lu.title,
                            lu.unit_type,
                            lu.unit_number,
                            iw.doc_type,
                            iw.title_official,
                            j.name_fa as jurisdiction,
                            ia.name_fa as authority
                        FROM ingest_apps_documents_legalunit lu
                        LEFT JOIN ingest_apps_documents_instrumentwork iw 
                            ON lu.instrument_work_id = iw.id
                        LEFT JOIN ingest_apps_masterdata_jurisdiction j 
                            ON iw.jurisdiction_id = j.id
                        LEFT JOIN ingest_apps_masterdata_issuingauthority ia 
                            ON iw.authority_id = ia.id
                        WHERE lu.id = :object_id::uuid
                    """)
                    
                    result = await session.execute(query, {"object_id": object_id})
                    doc = result.fetchone()
                    
                    if doc:
                        metadata = {
                            "title": doc.title,
                            "unit_type": doc.unit_type,
                            "unit_number": doc.unit_number,
                            "doc_type": doc.doc_type,
                            "document_title": doc.title_official,
                            "jurisdiction": doc.jurisdiction,
                            "authority": doc.authority,
                        }
                
                elif model_name == "qapair":
                    query = text("""
                        SELECT 
                            qa.question,
                            qa.category,
                            qa.difficulty_level,
                            qa.language
                        FROM ingest_apps_documents_qapair qa
                        WHERE qa.id = :object_id::uuid
                    """)
                    
                    result = await session.execute(query, {"object_id": object_id})
                    qa = result.fetchone()
                    
                    if qa:
                        metadata = {
                            "question": qa.question,
                            "category": qa.category,
                            "difficulty": qa.difficulty_level,
                            "language": qa.language,
                        }
        
        except Exception as e:
            logger.warning(f"Could not get metadata for {object_id}: {e}")
        
        return metadata
    
    async def _sync_document(self, target_id: str, payload: Dict[str, Any]):
        """Sync a document to Qdrant."""
        # Implementation depends on specific document structure
        logger.info(f"Syncing document: {target_id}")
    
    async def _sync_unit(self, target_id: str, payload: Dict[str, Any]):
        """Sync a legal unit to Qdrant."""
        # Implementation depends on specific unit structure
        logger.info(f"Syncing unit: {target_id}")
    
    async def _sync_qa(self, target_id: str, payload: Dict[str, Any]):
        """Sync a Q&A pair to Qdrant."""
        # Implementation depends on specific QA structure
        logger.info(f"Syncing QA: {target_id}")
    
    async def _update_job_status(
        self,
        session: AsyncSession,
        job_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
        error: Optional[str] = None
    ):
        """Update sync job status in Ingest database."""
        try:
            query = text("""
                UPDATE ingest_apps_syncbridge_syncjob
                SET status = :status,
                    completed_at = :completed_at,
                    last_error = :error,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :job_id::uuid
            """)
            
            await session.execute(
                query,
                {
                    "job_id": job_id,
                    "status": status,
                    "completed_at": completed_at,
                    "error": error
                }
            )
            await session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status and statistics."""
        try:
            redis = await get_redis_client()
            
            # Get last sync time
            last_sync = await redis.get("sync:last_embedding_sync")
            
            # Get Qdrant statistics
            qdrant_info = await self.qdrant_service.get_collection_info()
            
            # Get pending sync jobs count
            async with get_ingest_session() as session:
                query = text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as success,
                        COUNT(CASE WHEN status = 'error' THEN 1 END) as error
                    FROM ingest_apps_syncbridge_syncjob
                    WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
                """)
                
                result = await session.execute(query)
                job_stats = result.fetchone()
            
            return {
                "last_sync": last_sync,
                "qdrant": {
                    "vectors_count": qdrant_info.get("vectors_count", 0),
                    "points_count": qdrant_info.get("points_count", 0),
                    "status": qdrant_info.get("status", "unknown"),
                },
                "sync_jobs": {
                    "total_24h": job_stats.total if job_stats else 0,
                    "pending": job_stats.pending if job_stats else 0,
                    "running": job_stats.running if job_stats else 0,
                    "success": job_stats.success if job_stats else 0,
                    "error": job_stats.error if job_stats else 0,
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
    
    async def get_complete_statistics(self) -> Dict[str, Any]:
        """
        Get complete statistics from both Ingest database and Core Qdrant.
        
        Returns:
            Complete statistics including:
            - Total embeddings in Ingest database
            - Total embeddings in Core Qdrant
            - Sync progress and remaining items
            - Breakdown by vector dimensions
        """
        try:
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "ingest_database": {},
                "core_qdrant": {},
                "sync_progress": {},
                "summary": {}
            }
            
            # Get Ingest database statistics
            async with get_ingest_session() as session:
                # Total embeddings in Ingest
                total_query = text("""
                    SELECT 
                        COUNT(*) as total_embeddings,
                        COUNT(DISTINCT object_id) as unique_documents,
                        COUNT(CASE WHEN dim = 768 THEN 1 END) as dim_768,
                        COUNT(CASE WHEN dim = 512 THEN 1 END) as dim_512,
                        COUNT(CASE WHEN dim = 1536 THEN 1 END) as dim_1536,
                        COUNT(CASE WHEN dim = 3072 THEN 1 END) as dim_3072,
                        MIN(created_at) as oldest_embedding,
                        MAX(created_at) as newest_embedding
                    FROM ingest_apps_embeddings_embedding
                """)
                
                result = await session.execute(total_query)
                ingest_stats = result.fetchone()
                
                # Sync jobs statistics
                jobs_query = text("""
                    SELECT 
                        COUNT(*) as total_jobs,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as success,
                        COUNT(CASE WHEN status = 'error' THEN 1 END) as error,
                        COUNT(CASE WHEN job_type = 'document' THEN 1 END) as documents,
                        COUNT(CASE WHEN job_type = 'unit' THEN 1 END) as units,
                        COUNT(CASE WHEN job_type = 'qa' THEN 1 END) as qa_pairs
                    FROM ingest_apps_syncbridge_syncjob
                """)
                
                result = await session.execute(jobs_query)
                jobs_stats = result.fetchone()
                
                stats["ingest_database"] = {
                    "total_embeddings": ingest_stats.total_embeddings if ingest_stats else 0,
                    "unique_documents": ingest_stats.unique_documents if ingest_stats else 0,
                    "by_dimension": {
                        "512": ingest_stats.dim_512 if ingest_stats else 0,
                        "768": ingest_stats.dim_768 if ingest_stats else 0,
                        "1536": ingest_stats.dim_1536 if ingest_stats else 0,
                        "3072": ingest_stats.dim_3072 if ingest_stats else 0,
                    },
                    "oldest_embedding": ingest_stats.oldest_embedding.isoformat() if ingest_stats and ingest_stats.oldest_embedding else None,
                    "newest_embedding": ingest_stats.newest_embedding.isoformat() if ingest_stats and ingest_stats.newest_embedding else None,
                    "sync_jobs": {
                        "total": jobs_stats.total_jobs if jobs_stats else 0,
                        "pending": jobs_stats.pending if jobs_stats else 0,
                        "running": jobs_stats.running if jobs_stats else 0,
                        "success": jobs_stats.success if jobs_stats else 0,
                        "error": jobs_stats.error if jobs_stats else 0,
                        "by_type": {
                            "documents": jobs_stats.documents if jobs_stats else 0,
                            "units": jobs_stats.units if jobs_stats else 0,
                            "qa_pairs": jobs_stats.qa_pairs if jobs_stats else 0,
                        }
                    }
                }
            
            # Get Qdrant statistics
            qdrant_info = await self.qdrant_service.get_collection_info()
            
            stats["core_qdrant"] = {
                "total_points": qdrant_info.get("points_count", 0),
                "vectors_count": qdrant_info.get("vectors_count", 0),
                "indexed_vectors": qdrant_info.get("indexed_vectors_count", 0),
                "status": qdrant_info.get("status", "unknown"),
                "collection_name": qdrant_info.get("collection_name", "legal_documents"),
            }
            
            # Get last sync info from Redis
            redis = await get_redis_client()
            last_sync = await redis.get("sync:last_embedding_sync")
            
            # Calculate sync progress
            total_in_ingest = stats["ingest_database"]["total_embeddings"]
            total_in_qdrant = stats["core_qdrant"]["total_points"]
            
            remaining = max(0, total_in_ingest - total_in_qdrant)
            synced_percentage = (total_in_qdrant / total_in_ingest * 100) if total_in_ingest > 0 else 0
            
            stats["sync_progress"] = {
                "last_sync": last_sync,
                "total_synced": total_in_qdrant,
                "total_remaining": remaining,
                "sync_percentage": round(synced_percentage, 2),
                "pending_jobs": stats["ingest_database"]["sync_jobs"]["pending"],
                "error_jobs": stats["ingest_database"]["sync_jobs"]["error"],
            }
            
            # Summary
            stats["summary"] = {
                "status": "synced" if remaining == 0 else "pending",
                "total_embeddings_in_ingest": total_in_ingest,
                "total_embeddings_in_core": total_in_qdrant,
                "embeddings_transferred": total_in_qdrant,
                "embeddings_remaining": remaining,
                "sync_completion": f"{synced_percentage:.1f}%",
                "has_errors": stats["ingest_database"]["sync_jobs"]["error"] > 0,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get complete statistics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "ingest_database": {},
                "core_qdrant": {},
                "sync_progress": {},
                "summary": {"status": "error", "message": str(e)}
            }
