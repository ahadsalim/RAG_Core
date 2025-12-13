"""
Cohere Reranker Service
Reranks search results for better relevance
"""

from typing import List, Tuple, Optional
import cohere
import structlog

from app.config.settings import settings

logger = structlog.get_logger()


class CohereReranker:
    """Cohere-based reranking service."""
    
    def __init__(self):
        """Initialize Cohere client."""
        if not settings.cohere_api_key:
            raise ValueError("COHERE_API_KEY is required for reranking")
        
        self.client = cohere.Client(settings.cohere_api_key)
        self.model = settings.reranking_model
        logger.info(f"Cohere Reranker initialized with model: {self.model}")
    
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
                "Reranking completed",
                query_preview=query[:50],
                num_docs=len(documents),
                top_k=top_k,
                top_score=results[0][1] if results else 0
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")
            raise


def get_reranker() -> Optional[CohereReranker]:
    """Get reranker instance if configured."""
    if settings.cohere_api_key:
        try:
            return CohereReranker()
        except Exception as e:
            logger.warning(f"Failed to initialize reranker: {e}")
    return None
