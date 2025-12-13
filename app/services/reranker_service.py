"""
Reranker Service
Supports both local (sentence-transformers) and API-based (Cohere) reranking
"""

from typing import List, Tuple, Optional, Protocol
from abc import ABC, abstractmethod
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
    """Local reranker using sentence-transformers CrossEncoder."""
    
    def __init__(self, model_name: str = None):
        """
        Initialize local reranker with CrossEncoder model.
        
        Recommended models:
        - BAAI/bge-reranker-v2-m3 (multilingual, best for Persian)
        - BAAI/bge-reranker-base (English focused)
        - mixedbread-ai/mxbai-rerank-base-v1 (good multilingual)
        """
        from sentence_transformers import CrossEncoder
        import torch
        
        self.model_name = model_name or settings.reranking_model
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading local reranker model: {self.model_name} on {self.device}")
        
        self.model = CrossEncoder(
            self.model_name,
            max_length=512,
            device=self.device
        )
        
        logger.info(f"Local Reranker initialized: {self.model_name}")
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """Rerank documents using local CrossEncoder model."""
        if not documents:
            return []
        
        top_k = top_k or len(documents)
        
        try:
            # Create query-document pairs
            pairs = [[query, doc] for doc in documents]
            
            # Get scores from CrossEncoder
            scores = self.model.predict(pairs, show_progress_bar=False)
            
            # Create (index, score) tuples and sort by score descending
            indexed_scores = list(enumerate(scores))
            indexed_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k results
            results = [(idx, float(score)) for idx, score in indexed_scores[:top_k]]
            
            logger.debug(
                "Local reranking completed",
                query_preview=query[:50],
                num_docs=len(documents),
                top_k=top_k,
                top_score=results[0][1] if results else 0
            )
            
            return results
            
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
    2. If reranking_model is a HuggingFace model path -> Local CrossEncoder
    3. None if no valid configuration
    """
    model = settings.reranking_model
    
    # Check if it's a Cohere model
    if settings.cohere_api_key and model.startswith("rerank-"):
        try:
            return CohereReranker()
        except Exception as e:
            logger.warning(f"Failed to initialize Cohere reranker: {e}")
    
    # Check if it's a local model (HuggingFace path format)
    if "/" in model or model.startswith("BAAI") or model.startswith("mixedbread"):
        try:
            return LocalReranker(model)
        except Exception as e:
            logger.warning(f"Failed to initialize local reranker: {e}")
    
    logger.info("No reranker configured")
    return None
