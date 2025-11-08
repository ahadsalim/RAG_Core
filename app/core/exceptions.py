"""
Custom Exceptions for RAG Core System
Provides specific exception types for better error handling and debugging
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


# Base Exceptions
class RAGException(Exception):
    """Base exception for all RAG-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.error_code = error_code
        super().__init__(self.message)


class ServiceException(RAGException):
    """Base exception for service-level errors."""
    pass


# Database Exceptions
class DatabaseException(ServiceException):
    """Database operation failed."""
    pass


class RecordNotFoundException(DatabaseException):
    """Requested record not found in database."""
    pass


class DuplicateRecordException(DatabaseException):
    """Attempted to create duplicate record."""
    pass


# Embedding Exceptions
class EmbeddingException(ServiceException):
    """Base exception for embedding-related errors."""
    pass


class EmbeddingGenerationError(EmbeddingException):
    """Failed to generate embeddings."""
    pass


class InvalidEmbeddingDimensionError(EmbeddingException):
    """Embedding dimension mismatch."""
    pass


# Vector Database Exceptions
class VectorDatabaseException(ServiceException):
    """Base exception for vector database errors."""
    pass


class VectorSearchError(VectorDatabaseException):
    """Vector search operation failed."""
    pass


class VectorUpsertError(VectorDatabaseException):
    """Failed to upsert vectors to database."""
    pass


class CollectionNotFoundError(VectorDatabaseException):
    """Qdrant collection not found."""
    pass


# LLM Exceptions
class LLMException(ServiceException):
    """Base exception for LLM-related errors."""
    pass


class LLMGenerationError(LLMException):
    """LLM failed to generate response."""
    pass


class LLMConnectionError(LLMException):
    """Failed to connect to LLM service."""
    pass


class LLMRateLimitError(LLMException):
    """LLM rate limit exceeded."""
    pass


class InvalidLLMConfigError(LLMException):
    """Invalid LLM configuration."""
    pass


# Cache Exceptions
class CacheException(ServiceException):
    """Base exception for cache-related errors."""
    pass


class CacheConnectionError(CacheException):
    """Failed to connect to cache service."""
    pass


class CacheInvalidationError(CacheException):
    """Failed to invalidate cache."""
    pass


# Authentication & Authorization Exceptions
class AuthenticationException(RAGException):
    """Authentication failed."""
    pass


class AuthorizationException(RAGException):
    """User not authorized for this operation."""
    pass


class InvalidTokenException(AuthenticationException):
    """Invalid or expired token."""
    pass


class InvalidAPIKeyException(AuthenticationException):
    """Invalid API key."""
    pass


# Rate Limiting Exceptions
class RateLimitException(RAGException):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_type = limit_type


class DailyLimitExceeded(RateLimitException):
    """Daily query limit exceeded."""
    pass


class MinuteLimitExceeded(RateLimitException):
    """Per-minute rate limit exceeded."""
    pass


class HourLimitExceeded(RateLimitException):
    """Per-hour rate limit exceeded."""
    pass


# Validation Exceptions
class ValidationException(RAGException):
    """Input validation failed."""
    pass


class InvalidQueryException(ValidationException):
    """Query text is invalid."""
    pass


class InvalidFilterException(ValidationException):
    """Search filters are invalid."""
    pass


# Sync Exceptions
class SyncException(ServiceException):
    """Synchronization operation failed."""
    pass


class IngestConnectionError(SyncException):
    """Failed to connect to Ingest system."""
    pass


class SyncDataFormatError(SyncException):
    """Sync data format is invalid."""
    pass


# Helper function to convert exceptions to HTTP exceptions
def to_http_exception(exc: Exception) -> HTTPException:
    """
    Convert custom exceptions to FastAPI HTTPException.
    
    Args:
        exc: The exception to convert
        
    Returns:
        HTTPException with appropriate status code and detail
    """
    # Authentication/Authorization
    if isinstance(exc, InvalidTokenException):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if isinstance(exc, InvalidAPIKeyException):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    if isinstance(exc, AuthorizationException):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc)
        )
    
    # Rate Limiting
    if isinstance(exc, RateLimitException):
        headers = {}
        if hasattr(exc, 'retry_after') and exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers=headers
        )
    
    # Not Found
    if isinstance(exc, RecordNotFoundException):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        )
    
    # Validation
    if isinstance(exc, ValidationException):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        )
    
    # Duplicate
    if isinstance(exc, DuplicateRecordException):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        )
    
    # Service Unavailable
    if isinstance(exc, (
        EmbeddingGenerationError,
        VectorSearchError,
        LLMConnectionError,
        CacheConnectionError,
        IngestConnectionError
    )):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            headers={"Retry-After": "60"}
        )
    
    # LLM Rate Limit
    if isinstance(exc, LLMRateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "120"}
        )
    
    # Generic Service Error
    if isinstance(exc, ServiceException):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service error: {str(exc)}"
        )
    
    # Generic RAG Error
    if isinstance(exc, RAGException):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        )
    
    # Unknown error
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred"
    )
