"""
Local Embedding Service
Using sentence-transformers for local embeddings without external API
"""

from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import structlog
import torch

from app.config.settings import settings

logger = structlog.get_logger()


class LocalEmbeddingService:
    """Local embedding service using sentence-transformers."""
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize local embedding service."""
        self.model_name = model_name or settings.embedding_model
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(
            "Initializing local embedding service",
            model=self.model_name,
            device=self.device
        )
        
        try:
            # Load the model
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device
            )
            
            # Get embedding dimension
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                "Local embedding model loaded successfully",
                model=self.model_name,
                dimension=self.embedding_dim,
                device=self.device
            )
            
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def encode(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Encode texts to embeddings.
        
        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding
            normalize: Whether to normalize embeddings (recommended for cosine similarity)
            show_progress: Show progress bar
            
        Returns:
            numpy array of embeddings with shape (len(texts), embedding_dim)
        """
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )
            
            logger.debug(
                "Encoded texts to embeddings",
                num_texts=len(texts),
                embedding_shape=embeddings.shape
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
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
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        # Normalize if needed
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 > 0 and norm2 > 0:
            embedding1 = embedding1 / norm1
            embedding2 = embedding2 / norm2
        
        return float(np.dot(embedding1, embedding2))
    
    def batch_similarity(
        self,
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Calculate cosine similarity between query and multiple documents.
        
        Args:
            query_embedding: Query embedding with shape (embedding_dim,)
            doc_embeddings: Document embeddings with shape (num_docs, embedding_dim)
            
        Returns:
            numpy array of similarity scores with shape (num_docs,)
        """
        # Normalize query
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        
        # Normalize documents
        doc_norms = np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
        doc_embeddings_normalized = np.divide(
            doc_embeddings,
            doc_norms,
            where=doc_norms > 0
        )
        
        # Calculate similarities
        similarities = np.dot(doc_embeddings_normalized, query_embedding)
        
        return similarities


# Global instance
_embedding_service: Optional[LocalEmbeddingService] = None


def get_local_embedding_service() -> LocalEmbeddingService:
    """Get or create global embedding service instance."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = LocalEmbeddingService()
    
    return _embedding_service
