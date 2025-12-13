"""
Qdrant Vector Database Service
Handles all vector operations and semantic search
"""

from typing import List, Dict, Any, Optional, Tuple
import uuid
from datetime import datetime
import hashlib

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition,
    Range, MatchValue, SearchRequest, SearchParams, QuantizationSearchParams,
    CreateCollection, OptimizersConfigDiff, CollectionInfo,
    UpdateStatus, ScrollRequest, PointIdsList, Record
)
from qdrant_client.http.exceptions import UnexpectedResponse
import numpy as np
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class QdrantService:
    """Service for interacting with Qdrant vector database."""
    
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            grpc_port=settings.qdrant_grpc_port if settings.qdrant_use_grpc else None,
            api_key=settings.qdrant_api_key,
            prefer_grpc=settings.qdrant_use_grpc,
            https=False,  # Use HTTP not HTTPS
        )
        self.collection_name = settings.qdrant_collection
        
    def _to_point_id(self, point_id: Any) -> Any:
        """Normalize external point id (string) to Qdrant internal id used on upsert.
        Upsert converts string ids to 64-bit int derived from md5 (first 16 hex chars).
        Maintain same rule here to be able to retrieve the same record.
        """
        try:
            # If it's already an int-like, return as is
            if isinstance(point_id, int):
                return point_id
            # Try to parse as int string
            if isinstance(point_id, str) and point_id.isdigit():
                return int(point_id)
            # Convert string id to md5-based int used during upsert
            if isinstance(point_id, str):
                return int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)
        except Exception:
            pass
        return point_id

    async def health_check(self) -> bool:
        """Check if Qdrant is healthy."""
        try:
            # Try to get collection info
            self.client.get_collection(self.collection_name)
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
    
    async def init_collection(self):
        """Initialize Qdrant collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                # Create collection with multiple vector sizes support
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "default": VectorParams(
                            size=3072,  # For large embedding models (e.g., text-embedding-3-large)
                            distance=Distance.COSINE,
                        ),
                        "small": VectorParams(
                            size=512,  # Smaller models
                            distance=Distance.COSINE,
                        ),
                        "medium": VectorParams(
                            size=768,  # BERT-based models, e5-base (legacy)
                            distance=Distance.COSINE,
                        ),
                        "large": VectorParams(
                            size=1024,  # e5-large, bge-m3
                            distance=Distance.COSINE,
                        ),
                        "xlarge": VectorParams(
                            size=1536,  # OpenAI ada-002, text-embedding-3-small
                            distance=Distance.COSINE,
                        ),
                    },
                    optimizers_config=OptimizersConfigDiff(
                        indexing_threshold=20000,
                        memmap_threshold=50000,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")

                # Create indexes for better performance
                await self.create_indexes()
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")

        except Exception as e:
            # Do not fail application startup if Qdrant is temporarily unavailable
            logger.error(f"Failed to initialize Qdrant collection (will continue without Qdrant ready): {e}")
            return
    
    async def create_indexes(self):
        """Create payload indexes for filtering."""
        try:
            # Create indexes for common filter fields
            index_fields = [
                "document_id",
                "document_type",
                "chunk_index",
                "created_at",
                "language",
                "source",
                "metadata.category",
                "metadata.authority",
                "metadata.jurisdiction",
            ]
            
            for field in index_fields:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                    wait=True
                )
            
            logger.info("Created Qdrant payload indexes")
            
        except Exception as e:
            logger.warning(f"Could not create all indexes: {e}")
    
    async def upsert_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
        vector_field: str = "default"
    ) -> int:
        """
        Upsert embeddings to Qdrant.
        
        Args:
            embeddings: List of embedding dictionaries with structure:
                {
                    "id": str,
                    "vector": List[float],
                    "text": str,
                    "metadata": Dict[str, Any]
                }
            vector_field: Which vector field to use (default, small, medium, large)
            
        Returns:
            Number of embeddings upserted
        """
        try:
            points = []
            for emb in embeddings:
                # Generate UUID if not provided
                point_id = emb.get("id", str(uuid.uuid4()))
                if isinstance(point_id, str):
                    # Convert string to UUID-like int (consistent with _to_point_id)
                    point_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)
                
                # Prepare payload
                payload = {
                    "text": emb["text"],
                    "document_id": emb.get("document_id"),
                    "document_type": emb.get("document_type"),
                    "chunk_index": emb.get("chunk_index", 0),
                    "created_at": emb.get("created_at", datetime.utcnow().isoformat()),
                    "language": emb.get("language", "fa"),
                    "source": emb.get("source", "ingest"),
                    "metadata": emb.get("metadata", {}),
                }
                
                # Create point
                point = PointStruct(
                    id=point_id,
                    vector={vector_field: emb["vector"]},
                    payload=payload
                )
                points.append(point)
            
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                    wait=True
                )
            
            logger.info(f"Upserted {len(points)} embeddings to Qdrant")
            return len(points)
            
        except Exception as e:
            logger.error(f"Failed to upsert embeddings: {e}")
            raise

    async def get_point(self, point_id: Any, with_vectors: bool = True) -> Dict[str, Any]:
        """
        Retrieve a single point (node) by id with full payload and vectors.
        """
        try:
            qid = self._to_point_id(point_id)
            records = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[qid],
                with_payload=True,
                with_vectors=with_vectors,
            )
            if not records:
                return {}
            rec = records[0]
            # rec is Record(id=..., payload=..., vector=...)
            return {
                "id": str(rec.id),
                "payload": rec.payload or {},
                "vectors": rec.vector if with_vectors else None,
            }
        except Exception as e:
            logger.error(f"Failed to retrieve point {point_id}: {e}")
            raise
    
    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        vector_field: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in Qdrant.
        
        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filters: Optional filters for search
            vector_field: Which vector field to search
            
        Returns:
            List of search results with scores
        """
        try:
            # Build filter conditions
            filter_conditions = []
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        # Range filter
                        if "gte" in value and "lte" in value:
                            filter_conditions.append(
                                FieldCondition(
                                    key=key,
                                    range=Range(
                                        gte=value["gte"],
                                        lte=value["lte"]
                                    )
                                )
                            )
                    else:
                        # Exact match
                        filter_conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value)
                            )
                        )
            
            # Perform search
            search_filter = Filter(must=filter_conditions) if filter_conditions else None
            
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=vector_field,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=search_filter,
                with_payload=True,
            ).points
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": str(result.id),
                    "score": result.score,
                    "text": result.payload.get("text", ""),
                    "document_id": result.payload.get("document_id"),
                    "metadata": result.payload.get("metadata", {}),
                    "source": result.payload.get("source"),
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    async def hybrid_search(
        self,
        query_vector: List[float],
        query_text: str,
        limit: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None,
        vector_field: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and keyword search.
        
        NOTE: Qdrant's keyword search با FieldCondition.match فقط exact match را پشتیبانی می‌کند
        و برای full-text search مناسب نیست. در حال حاضر فقط از vector search استفاده می‌کنیم.
        
        Args:
            query_vector: Query embedding vector
            query_text: Query text for keyword search (currently unused)
            limit: Maximum number of results
            vector_weight: Weight for vector search results (currently 1.0)
            keyword_weight: Weight for keyword search results (currently 0.0)
            filters: Optional filters
            vector_field: Which vector field to search
            
        Returns:
            Search results (currently vector-only)
        """
        try:
            # فعلاً فقط از vector search استفاده می‌کنیم
            # چون keyword search در Qdrant برای فارسی مناسب نیست
            logger.debug(
                "Hybrid search called (using vector-only for now)",
                query_text=query_text[:50],
                limit=limit
            )
            
            # Vector search با threshold پایین‌تر
            vector_results = await self.search(
                query_vector=query_vector,
                limit=limit,
                score_threshold=0.4,  # Lower threshold for better recall
                filters=filters,
                vector_field=vector_field
            )
            
            # Return vector results as-is
            # در آینده می‌توانیم BM25 یا full-text search خارجی اضافه کنیم
            return vector_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    async def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete all vectors for a specific document.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            Number of vectors deleted
        """
        try:
            # Delete points with matching document_id
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                wait=True
            )
            
            logger.info(f"Deleted vectors for document: {document_id}")
            return 1  # Qdrant doesn't return count
            
        except Exception as e:
            logger.error(f"Failed to delete document vectors: {e}")
            raise
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information and statistics."""
        try:
            info = self.client.get_collection(self.collection_name)
            
            return {
                "status": info.status,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "config": {
                    "params": info.config.params,
                    "optimizer_config": info.config.optimizer_config,
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise
    
    async def optimize_collection(self):
        """Optimize collection for better performance."""
        try:
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=OptimizersConfigDiff(
                    indexing_threshold=10000,
                    memmap_threshold=20000,
                )
            )
            
            logger.info(f"Optimized collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to optimize collection: {e}")
            raise
