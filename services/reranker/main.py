"""
Local Reranker Service
Standalone FastAPI service for document reranking using BAAI/bge-reranker-v2-m3
"""

import os
import logging
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", "/models/reranker")
MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))

# Global model instance
reranker_model = None


class RerankRequest(BaseModel):
    """Request model for reranking."""
    query: str
    documents: List[str]
    top_k: Optional[int] = None


class RerankResult(BaseModel):
    """Single rerank result."""
    index: int
    score: float
    text: Optional[str] = None


class RerankResponse(BaseModel):
    """Response model for reranking."""
    results: List[RerankResult]
    model: str


def load_model():
    """Load the reranker model."""
    global reranker_model
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading reranker model: {MODEL_NAME} on {device}")
    
    # Check if model exists locally
    if os.path.exists(MODEL_PATH) and os.listdir(MODEL_PATH):
        logger.info(f"Loading model from local path: {MODEL_PATH}")
        model_location = MODEL_PATH
    else:
        logger.info(f"Downloading model from HuggingFace: {MODEL_NAME}")
        model_location = MODEL_NAME
    
    reranker_model = CrossEncoder(
        model_location,
        max_length=MAX_LENGTH,
        device=device
    )
    
    # Save model locally if downloaded from HuggingFace
    if model_location == MODEL_NAME and not os.path.exists(MODEL_PATH):
        os.makedirs(MODEL_PATH, exist_ok=True)
        reranker_model.save(MODEL_PATH)
        logger.info(f"Model saved to: {MODEL_PATH}")
    
    logger.info(f"Reranker model loaded successfully on {device}")
    return reranker_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Reranker Service...")
    load_model()
    logger.info("Reranker Service ready!")
    yield
    # Shutdown
    logger.info("Shutting down Reranker Service...")


app = FastAPI(
    title="Local Reranker Service",
    description="Document reranking service using BAAI/bge-reranker-v2-m3",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "model_loaded": reranker_model is not None,
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    }


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """
    Rerank documents based on relevance to query.
    
    Args:
        request: RerankRequest with query and documents
        
    Returns:
        RerankResponse with sorted results by relevance score
    """
    if reranker_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    if not request.documents:
        return RerankResponse(results=[], model=MODEL_NAME)
    
    try:
        # Create query-document pairs
        pairs = [[request.query, doc] for doc in request.documents]
        
        # Get scores from CrossEncoder
        scores = reranker_model.predict(pairs, show_progress_bar=False)
        
        # Create indexed scores and sort by score descending
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Apply top_k limit
        top_k = request.top_k or len(request.documents)
        indexed_scores = indexed_scores[:top_k]
        
        # Build response
        results = [
            RerankResult(
                index=idx,
                score=float(score),
                text=request.documents[idx][:200] if len(request.documents[idx]) > 200 else request.documents[idx]
            )
            for idx, score in indexed_scores
        ]
        
        logger.debug(f"Reranked {len(request.documents)} documents, top score: {results[0].score if results else 0}")
        
        return RerankResponse(results=results, model=MODEL_NAME)
        
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
