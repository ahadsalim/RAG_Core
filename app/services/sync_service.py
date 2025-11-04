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
        Get complete statistics from Core PostgreSQL and Qdrant.
        
        Returns:
            Complete statistics including:
            - User and conversation data from PostgreSQL
            - Vector embeddings from Qdrant
            - Cache and feedback statistics
        """
        try:
            from app.db.session import get_session
            from sqlalchemy import text, func
            from app.models.user import UserProfile, Conversation, Message, QueryCache, UserFeedback
            
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "postgresql": {},
                "qdrant": {},
                "summary": {}
            }
            
            # Get PostgreSQL statistics
            async with get_session() as session:
                # User statistics
                user_count = await session.scalar(
                    text("SELECT COUNT(*) FROM user_profiles WHERE is_active = true")
                )
                
                user_by_tier = await session.execute(
                    text("""
                        SELECT tier, COUNT(*) as count 
                        FROM user_profiles 
                        WHERE is_active = true
                        GROUP BY tier
                    """)
                )
                tier_stats = {row.tier: row.count for row in user_by_tier}
                
                # Conversation statistics
                conversation_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_conversations,
                            SUM(message_count) as total_messages,
                            AVG(message_count) as avg_messages_per_conversation
                        FROM conversations
                        WHERE is_active = true
                    """)
                )
                conv_data = conversation_stats.fetchone()
                
                # Message statistics
                message_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_messages,
                            COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                            COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages,
                            SUM(tokens) as total_tokens,
                            AVG(processing_time_ms) as avg_processing_time
                        FROM messages
                        WHERE is_active = true
                    """)
                )
                msg_data = message_stats.fetchone()
                
                # Cache statistics
                cache_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_cached,
                            SUM(hit_count) as total_hits,
                            COUNT(CASE WHEN expires_at > NOW() THEN 1 END) as active_cache
                        FROM query_cache
                        WHERE is_active = true
                    """)
                )
                cache_data = cache_stats.fetchone()
                
                # Feedback statistics
                feedback_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_feedback,
                            AVG(rating) as avg_rating,
                            COUNT(CASE WHEN processed = true THEN 1 END) as processed_feedback
                        FROM user_feedback
                        WHERE is_active = true
                    """)
                )
                feedback_data = feedback_stats.fetchone()
                
                stats["postgresql"] = {
                    "users": {
                        "total": user_count or 0,
                        "by_tier": tier_stats,
                    },
                    "conversations": {
                        "total": conv_data.total_conversations if conv_data else 0,
                        "total_messages_in_conversations": conv_data.total_messages if conv_data else 0,
                        "avg_messages_per_conversation": float(conv_data.avg_messages_per_conversation) if conv_data and conv_data.avg_messages_per_conversation else 0,
                    },
                    "messages": {
                        "total": msg_data.total_messages if msg_data else 0,
                        "user_messages": msg_data.user_messages if msg_data else 0,
                        "assistant_messages": msg_data.assistant_messages if msg_data else 0,
                        "total_tokens": msg_data.total_tokens if msg_data else 0,
                        "avg_processing_time_ms": float(msg_data.avg_processing_time) if msg_data and msg_data.avg_processing_time else 0,
                    },
                    "cache": {
                        "total_cached_queries": cache_data.total_cached if cache_data else 0,
                        "total_cache_hits": cache_data.total_hits if cache_data else 0,
                        "active_cache_entries": cache_data.active_cache if cache_data else 0,
                    },
                    "feedback": {
                        "total": feedback_data.total_feedback if feedback_data else 0,
                        "avg_rating": float(feedback_data.avg_rating) if feedback_data and feedback_data.avg_rating else 0,
                        "processed": feedback_data.processed_feedback if feedback_data else 0,
                    }
                }
            
            # Get Qdrant statistics
            qdrant_info = await self.qdrant_service.get_collection_info()
            
            stats["qdrant"] = {
                "total_points": qdrant_info.get("points_count", 0),
                "vectors_count": qdrant_info.get("vectors_count", 0),
                "indexed_vectors": qdrant_info.get("indexed_vectors_count", 0),
                "status": qdrant_info.get("status", "unknown"),
                "collection_name": qdrant_info.get("collection_name", "legal_documents"),
            }
            
            # Summary
            stats["summary"] = {
                "total_users": stats["postgresql"]["users"]["total"],
                "total_conversations": stats["postgresql"]["conversations"]["total"],
                "total_messages": stats["postgresql"]["messages"]["total"],
                "total_vectors_in_qdrant": stats["qdrant"]["total_points"],
                "total_cached_queries": stats["postgresql"]["cache"]["total_cached_queries"],
                "avg_user_rating": stats["postgresql"]["feedback"]["avg_rating"],
                "qdrant_status": stats["qdrant"]["status"],
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get complete statistics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "postgresql": {},
                "qdrant": {},
                "summary": {"status": "error", "message": str(e)}
            }
