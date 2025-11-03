"""
Embedding API Endpoints
Local embedding service for text vectorization
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import structlog

from app.services.local_embedding_service import get_local_embedding_service

logger = structlog.get_logger()
router = APIRouter()


class EmbeddingRequest(BaseModel):
    """Request model for embedding generation."""
    input: str | List[str] = Field(..., description="Text or list of texts to embed")
    model: str = Field(default="", description="Model name (optional, uses default)")


class EmbeddingData(BaseModel):
    """Single embedding data."""
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingUsage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Response model for embeddings (OpenAI-compatible format)."""
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


@router.post("/embeddings", response_model=EmbeddingResponse, tags=["Embeddings"])
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """
    Create embeddings for input text(s).
    
    This endpoint is compatible with OpenAI's embedding API format,
    allowing drop-in replacement for OpenAI embeddings.
    
    Example:
    ```json
    {
        "input": "سلام، این یک متن فارسی است",
        "model": "intfloat/multilingual-e5-base"
    }
    ```
    """
    try:
        # Get embedding service
        embedding_service = get_local_embedding_service()
        
        # Handle both string and list inputs
        if isinstance(request.input, str):
            texts = [request.input]
        else:
            texts = request.input
        
        # Generate embeddings
        embeddings = embedding_service.encode(texts, normalize=True)
        
        # Prepare response in OpenAI format
        data = [
            EmbeddingData(
                embedding=embedding.tolist(),
                index=i
            )
            for i, embedding in enumerate(embeddings)
        ]
        
        # Estimate token usage (rough approximation)
        total_chars = sum(len(text) for text in texts)
        prompt_tokens = total_chars // 4  # Rough estimate
        
        response = EmbeddingResponse(
            data=data,
            model=request.model or embedding_service.model_name,
            usage=EmbeddingUsage(
                prompt_tokens=prompt_tokens,
                total_tokens=prompt_tokens
            )
        )
        
        logger.info(
            "Generated embeddings",
            num_texts=len(texts),
            embedding_dim=len(data[0].embedding) if data else 0
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embeddings: {str(e)}"
        )


@router.get("/embeddings/info", tags=["Embeddings"])
async def get_embedding_info() -> Dict[str, Any]:
    """
    Get information about the embedding service.
    
    Returns model name, dimension, and device information.
    """
    try:
        embedding_service = get_local_embedding_service()
        
        return {
            "model": embedding_service.model_name,
            "dimension": embedding_service.embedding_dim,
            "device": embedding_service.device,
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Failed to get embedding info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding info: {str(e)}"
        )


class SimilarityRequest(BaseModel):
    """Request model for similarity calculation."""
    text1: str = Field(..., description="First text")
    text2: str = Field(..., description="Second text")


@router.post("/embeddings/similarity", tags=["Embeddings"])
async def calculate_similarity(request: SimilarityRequest) -> Dict[str, Any]:
    """
    Calculate cosine similarity between two texts.
    
    Returns a similarity score between -1 and 1.
    """
    try:
        embedding_service = get_local_embedding_service()
        
        # Generate embeddings
        embeddings = embedding_service.encode([request.text1, request.text2])
        
        # Calculate similarity
        similarity = embedding_service.similarity(embeddings[0], embeddings[1])
        
        return {
            "text1": request.text1,
            "text2": request.text2,
            "similarity": float(similarity),
            "model": embedding_service.model_name
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate similarity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate similarity: {str(e)}"
        )
