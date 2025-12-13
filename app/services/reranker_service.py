"""
Reranker Service
Supports local reranker service (Docker container) and Cohere API
"""

from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
import httpx
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class BaseReranker(ABC):
    """Abstract base class for rerankers."""
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents based on relevance to query.
        
        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (default: all)
            
        Returns:
            List of (original_index, relevance_score) tuples, sorted by score descending
        """
        pass


class LocalReranker(BaseReranker):
    """Local reranker using standalone Docker service."""
    
    def __init__(self, service_url: str = None):
        """
        Initialize local reranker client.
        
        Args:
            service_url: URL of the reranker service (default: http://reranker:8100)
        """
        self.service_url = service_url or settings.reranker_service_url
        self.timeout = 30.0
        logger.info(f"Local Reranker initialized: {self.service_url}")
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """Rerank documents using local reranker service."""
        if not documents:
            return []
        
        top_k = top_k or len(documents)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.service_url}/rerank",
                    json={
                        "query": query,
                        "documents": documents,
                        "top_k": top_k
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            # Extract results
            results = [(r["index"], r["score"]) for r in data["results"]]
            
            logger.debug(
                "Local reranking completed",
                query_preview=query[:50],
                num_docs=len(documents),
                top_k=top_k,
                top_score=results[0][1] if results else 0
            )
            
            return results
            
        except httpx.ConnectError:
            logger.warning("Reranker service not available, skipping reranking")
            return [(i, 1.0) for i in range(min(top_k, len(documents)))]
        except Exception as e:
            logger.error(f"Local reranking failed: {e}")
            raise


class CohereReranker(BaseReranker):
    """Cohere API-based reranking service."""
    
    def __init__(self):
        """Initialize Cohere client."""
        import cohere
        
        if not settings.cohere_api_key:
            raise ValueError("COHERE_API_KEY is required for Cohere reranking")
        
        self.client = cohere.Client(settings.cohere_api_key)
        self.model = settings.reranking_model
        logger.info(f"Cohere Reranker initialized with model: {self.model}")
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """Rerank documents using Cohere API."""
        if not documents:
            return []
        
        top_k = top_k or len(documents)
        
        try:
            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=min(top_k, len(documents)),
                return_documents=False
            )
            
            results = []
            for result in response.results:
                results.append((result.index, result.relevance_score))
            
            logger.debug(
                "Cohere reranking completed",
                query_preview=query[:50],
                num_docs=len(documents),
                top_k=top_k,
                top_score=results[0][1] if results else 0
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")
            raise


def get_reranker() -> Optional[BaseReranker]:
    """
    Get reranker instance based on configuration.
    
    Priority:
    1. If COHERE_API_KEY is set and reranking_model starts with 'rerank-' -> Cohere
    2. If reranker_service_url is configured -> Local Docker service
    3. None if no valid configuration
    """
    model = settings.reranking_model
    
    # Check if it's a Cohere model
    if settings.cohere_api_key and model.startswith("rerank-"):
        try:
            return CohereReranker()
        except Exception as e:
            logger.warning(f"Failed to initialize Cohere reranker: {e}")
    
    # Check if local reranker service is configured
    if settings.reranker_service_url:
        try:
            return LocalReranker(settings.reranker_service_url)
        except Exception as e:
            logger.warning(f"Failed to initialize local reranker: {e}")
    
    logger.info("No reranker configured")
    return None
