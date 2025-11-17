"""
Unified Embedding Service
Automatically switches between API-based and local embeddings based on configuration
"""

from typing import List, Optional
import numpy as np
import structlog
from openai import OpenAI

from app.config.settings import settings
from app.services.local_embedding_service import LocalEmbeddingService

logger = structlog.get_logger()


class EmbeddingService:
    """
    Unified embedding service that automatically chooses between:
    - API-based embeddings (OpenAI, etc.) if EMBEDDING_API_KEY is set
    - Local embeddings (sentence-transformers) if no API key
    """
    
    def __init__(self):
        """Initialize embedding service based on configuration."""
        self.use_api = bool(settings.embedding_api_key and settings.embedding_api_key.strip())
        
        if self.use_api:
            # Use API-based embeddings
            self.mode = "api"
            self.client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url if settings.embedding_base_url else None
            )
            self.model = settings.embedding_model
            
            logger.info(
                "Embedding service initialized in API mode",
                model=self.model,
                base_url=settings.embedding_base_url or "OpenAI default"
            )
            
            # Get dimension from model
            self.embedding_dim = self._get_api_dimension()
            
        else:
            # Use local embeddings
            self.mode = "local"
            self.local_service = LocalEmbeddingService(model_name=settings.embedding_model)
            self.embedding_dim = self.local_service.get_embedding_dimension()
            
            logger.warning(
                "⚠️  Embedding service initialized in LOCAL mode",
                model=settings.embedding_model,
                dimension=self.embedding_dim,
                message="IMPORTANT: If you change embedding model, you MUST re-embed all chunks!"
            )
    
    def _get_api_dimension(self) -> int:
        """Get embedding dimension for API models."""
        # Common OpenAI models
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        
        # Check if model is in known list
        if self.model in dimensions:
            return dimensions[self.model]
        
        # For unknown models, try to get dimension from API
        try:
            response = self.client.embeddings.create(
                input="test",
                model=self.model
            )
            return len(response.data[0].embedding)
        except Exception as e:
            logger.warning(f"Could not determine embedding dimension, defaulting to 1536: {e}")
            return 1536
    
    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Encode texts to embeddings.
        
        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding (used in local mode)
            normalize: Whether to normalize embeddings
            
        Returns:
            numpy array of embeddings with shape (len(texts), embedding_dim)
        """
        if self.mode == "api":
            return self._encode_api(texts, normalize)
        else:
            return self.local_service.encode(texts, batch_size, normalize)
    
    def _encode_api(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """Encode using API."""
        try:
            # Process in batches to avoid API limits
            all_embeddings = []
            batch_size = 100  # API batch size
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            
            embeddings = np.array(all_embeddings, dtype=np.float32)
            
            # Normalize if requested
            if normalize:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = np.divide(embeddings, norms, where=norms > 0)
            
            logger.debug(
                "Encoded texts using API",
                num_texts=len(texts),
                embedding_shape=embeddings.shape
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"API embedding failed: {e}")
            raise
    
    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Encode a single text to embedding.
        
        Args:
            text: Text to encode
            normalize: Whether to normalize embedding
            
        Returns:
            numpy array of embedding with shape (embedding_dim,)
        """
        return self.encode([text], normalize=normalize)[0]
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.embedding_dim
    
    def get_mode(self) -> str:
        """Get current mode (api or local)."""
        return self.mode
    
    def get_model_name(self) -> str:
        """Get current model name."""
        return self.model if self.mode == "api" else settings.embedding_model


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service instance."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
        
        # Log warning if using local mode
        if _embedding_service.get_mode() == "local":
            logger.warning(
                "="*60 + "\n" +
                "⚠️  IMPORTANT: Using LOCAL embedding model\n" +
                f"Model: {_embedding_service.get_model_name()}\n" +
                f"Dimension: {_embedding_service.get_embedding_dimension()}\n" +
                "\n" +
                "If you change the embedding model, you MUST:\n" +
                "1. Re-embed all existing chunks in Ingest system\n" +
                "2. Re-sync all embeddings to Core system\n" +
                "3. Clear Qdrant collection and rebuild\n" +
                "\n" +
                "To use API-based embeddings instead, set in .env:\n" +
                "  EMBEDDING_API_KEY=your-api-key\n" +
                "  EMBEDDING_BASE_URL=https://api.openai.com/v1  (optional)\n" +
                "="*60
            )
    
    return _embedding_service


def reset_embedding_service():
    """Reset global embedding service (useful for testing or config changes)."""
    global _embedding_service
    _embedding_service = None
