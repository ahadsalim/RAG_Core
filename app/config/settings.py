"""
Core System Configuration
Central configuration management using Pydantic Settings
"""

from typing import List, Optional, Literal
from functools import lru_cache
from pydantic import Field, field_validator, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",  # Allow extra fields from .env
    )
    
    # Application
    app_name: str = Field(default="RAG Core System")
    app_version: str = Field(default="1.0.0")
    environment: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=7001)
    workers: int = Field(default=4)
    reload: bool = Field(default=False)
    domain_name: Optional[str] = Field(default=None, description="Production domain name")
    
    # Security
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    
    # CORS
    cors_origins: List[str] = Field(default_factory=list)
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: List[str] = Field(default=["*"])
    cors_allow_headers: List[str] = Field(default=["*"])
    
    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    # Database - Core DB
    database_url: PostgresDsn
    database_pool_size: int = Field(default=20, ge=1)
    database_max_overflow: int = Field(default=40, ge=0)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_echo: bool = Field(default=False)
    
    # Ingest Database (Read-only)
    ingest_database_url: Optional[str] = Field(default=None)
    ingest_database_pool_size: int = Field(default=10, ge=1)
    
    @field_validator('ingest_database_url', mode='before')
    @classmethod
    def validate_ingest_db_url(cls, v):
        """Allow empty string for ingest_database_url."""
        if v == "" or v is None:
            return None
        return v
    
    # Qdrant Vector Database
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=7333)
    qdrant_grpc_port: int = Field(default=7334)
    qdrant_api_key: Optional[str] = Field(default=None)
    qdrant_collection: str = Field(default="legal_documents")
    qdrant_use_grpc: bool = Field(default=True)
    
    # Redis
    redis_url: RedisDsn
    redis_password: Optional[str] = Field(default=None)
    redis_max_connections: int = Field(default=50, ge=1)
    redis_decode_responses: bool = Field(default=True)
    
    # Cache Settings
    cache_ttl_default: int = Field(default=3600, ge=0)
    cache_ttl_query: int = Field(default=7200, ge=0)
    cache_ttl_embedding: int = Field(default=86400, ge=0)
    semantic_cache_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    
    # Celery
    celery_broker_url: RedisDsn
    celery_result_backend: RedisDsn
    celery_task_serializer: str = Field(default="json")
    celery_result_serializer: str = Field(default="json")
    celery_accept_content: List[str] = Field(default=["json"])
    celery_timezone: str = Field(default="Asia/Tehran")
    celery_enable_utc: bool = Field(default=False)
    
    # LLM Configuration (Unified for OpenAI-compatible APIs)
    llm_api_key: Optional[str] = Field(default=None, description="API Key or Token for LLM")
    llm_base_url: Optional[str] = Field(default=None, description="Base URL for OpenAI-compatible API")
    llm_model: str = Field(default="gpt-4-turbo-preview", description="Model name")
    llm_max_tokens: int = Field(default=4096, ge=1, description="Maximum output tokens")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature for generation")
    
    # LLM Classification (for query categorization)
    enable_query_classification: bool = Field(default=True, description="Enable query classification (can disable for faster response)")
    llm_classification_api_key: Optional[str] = Field(default=None, description="API Key for classification LLM")
    llm_classification_base_url: Optional[str] = Field(default=None, description="Base URL for classification LLM")
    llm_classification_model: Optional[str] = Field(default=None, description="Model for classification")
    llm_classification_max_tokens: int = Field(default=512, ge=1, description="Max tokens for classification")
    llm_classification_temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Temperature for classification")
    
    # Embedding Configuration
    embedding_model: str = Field(default="intfloat/multilingual-e5-large", description="Embedding model name")
    embedding_dim: int = Field(default=1024, ge=128, description="Embedding dimension (must match model)")
    embedding_api_key: Optional[str] = Field(default=None, description="API Key for embeddings (if different)")
    embedding_base_url: Optional[str] = Field(default=None, description="Base URL for embeddings (if different)")
    
    # Reranking
    cohere_api_key: Optional[str] = Field(default=None)
    reranking_model: str = Field(default="rerank-multilingual-v2.0")
    reranking_top_k: int = Field(default=10, ge=1)
    
    # Voice Processing
    whisper_model: str = Field(default="large-v3")
    whisper_device: Literal["cuda", "cpu"] = Field(default="cpu")
    whisper_compute_type: str = Field(default="float16")
    max_audio_size_mb: int = Field(default=25, ge=1)
    
    # OCR Settings
    ocr_language: str = Field(default="fas+eng")
    tesseract_cmd: str = Field(default="/usr/bin/tesseract")
    max_image_size_mb: int = Field(default=10, ge=1)
    
    # RAG Settings
    rag_chunk_size: int = Field(default=512, ge=100)
    rag_chunk_overlap: int = Field(default=50, ge=0)
    rag_top_k_retrieval: int = Field(default=20, ge=1)
    rag_top_k_rerank: int = Field(default=5, ge=1)
    rag_similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    rag_max_context_length: int = Field(default=8192, ge=100)
    rag_use_hybrid_search: bool = Field(default=True)
    rag_bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    rag_vector_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Search Settings
    search_max_results: int = Field(default=50, ge=1)
    search_timeout: int = Field(default=30, ge=1)
    fuzzy_match_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_per_hour: int = Field(default=1000, ge=1)
    rate_limit_per_day: int = Field(default=10000, ge=1)
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)
    sentry_dsn: Optional[str] = Field(default=None)
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    
    # File Storage (S3/MinIO)
    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_access_key_id: str = Field(default="minioadmin")
    s3_secret_access_key: str = Field(default="minioadmin")
    s3_bucket_name: str = Field(default="core-storage")
    s3_region: str = Field(default="us-east-1")
    s3_use_ssl: bool = Field(default=False)
    
    # External Services
    ingest_api_url: str = Field(default="http://localhost:8000/api")
    ingest_api_key: Optional[str] = Field(default=None)
    users_api_url: str = Field(default="http://localhost:3001/api")
    users_api_key: Optional[str] = Field(default=None)
    
    # Feature Flags
    enable_voice_search: bool = Field(default=True)
    enable_image_search: bool = Field(default=True)
    enable_semantic_cache: bool = Field(default=True)
    enable_audit_log: bool = Field(default=True)
    enable_content_filter: bool = Field(default=True)
    enable_streaming: bool = Field(default=True)
    
    # Content Filtering
    content_filter_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    blocked_keywords: List[str] = Field(default_factory=list)
    max_response_length: int = Field(default=10000, ge=100)
    
    @field_validator("blocked_keywords", mode="before")
    def parse_blocked_keywords(cls, v):
        if isinstance(v, str):
            return [kw.strip() for kw in v.split(",") if kw.strip()]
        return v
    
    # System Limits
    max_concurrent_requests: int = Field(default=100, ge=1)
    max_history_length: int = Field(default=50, ge=1)
    max_query_length: int = Field(default=2000, ge=100)
    request_timeout: int = Field(default=60, ge=1)
    
    # Backup
    backup_enabled: bool = Field(default=True)
    backup_schedule: str = Field(default="0 2 * * *")
    backup_retention_days: int = Field(default=30, ge=1)
    backup_path: str = Field(default="/backups")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
