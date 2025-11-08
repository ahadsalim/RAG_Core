"""
Prometheus Metrics for RAG Core System
Comprehensive metrics for monitoring system performance
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import structlog

logger = structlog.get_logger()

# ============================================================================
# Query Processing Metrics
# ============================================================================

# Total queries processed
query_total = Counter(
    'rag_queries_total',
    'Total number of queries processed',
    ['status', 'user_tier', 'language']
)

# Query processing duration
query_duration = Histogram(
    'rag_query_duration_seconds',
    'Query processing duration in seconds',
    ['stage'],  # stages: total, embedding, retrieval, reranking, generation
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Tokens used
tokens_used = Counter(
    'rag_tokens_used_total',
    'Total tokens used for LLM generation',
    ['model', 'user_tier']
)

# Query errors
query_errors = Counter(
    'rag_query_errors_total',
    'Total query processing errors',
    ['error_type', 'stage']
)

# ============================================================================
# Cache Metrics
# ============================================================================

# Cache hits/misses
cache_operations = Counter(
    'rag_cache_operations_total',
    'Cache operations',
    ['operation', 'layer', 'result']  # operation: get/set, layer: memory/redis/db, result: hit/miss
)

# Cache hit rate (gauge updated periodically)
cache_hit_rate = Gauge(
    'rag_cache_hit_rate',
    'Cache hit rate',
    ['layer']
)

# Cache size
cache_size = Gauge(
    'rag_cache_size',
    'Current cache size',
    ['layer']
)

# ============================================================================
# Rate Limiting Metrics
# ============================================================================

# Rate limit violations
rate_limit_violations = Counter(
    'rag_rate_limit_violations_total',
    'Rate limit violations',
    ['limit_type', 'user_tier']  # limit_type: minute/hour/day
)

# Active users
active_users = Gauge(
    'rag_active_users',
    'Number of active users',
    ['tier', 'time_window']  # time_window: 1h/24h/7d
)

# ============================================================================
# Vector Database Metrics
# ============================================================================

# Qdrant operations
qdrant_operations = Counter(
    'rag_qdrant_operations_total',
    'Qdrant operations',
    ['operation', 'status']  # operation: search/upsert/delete, status: success/error
)

# Qdrant search duration
qdrant_search_duration = Histogram(
    'rag_qdrant_search_duration_seconds',
    'Qdrant search duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# Qdrant collection size
qdrant_collection_size = Gauge(
    'rag_qdrant_collection_size',
    'Number of vectors in Qdrant collection'
)

# Retrieved chunks
retrieved_chunks = Histogram(
    'rag_retrieved_chunks',
    'Number of chunks retrieved per query',
    buckets=[1, 3, 5, 10, 20, 50, 100]
)

# ============================================================================
# LLM Metrics
# ============================================================================

# LLM requests
llm_requests = Counter(
    'rag_llm_requests_total',
    'LLM API requests',
    ['provider', 'model', 'status']
)

# LLM latency
llm_latency = Histogram(
    'rag_llm_latency_seconds',
    'LLM API latency',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# LLM errors
llm_errors = Counter(
    'rag_llm_errors_total',
    'LLM API errors',
    ['provider', 'model', 'error_type']
)

# ============================================================================
# Embedding Metrics
# ============================================================================

# Embedding generation
embedding_generation = Counter(
    'rag_embedding_generation_total',
    'Embedding generation operations',
    ['model', 'status']
)

# Embedding latency
embedding_latency = Histogram(
    'rag_embedding_latency_seconds',
    'Embedding generation latency',
    ['model'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# ============================================================================
# Database Metrics
# ============================================================================

# Database queries
db_queries = Counter(
    'rag_db_queries_total',
    'Database queries',
    ['operation', 'table', 'status']
)

# Database query duration
db_query_duration = Histogram(
    'rag_db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Active database connections
db_connections = Gauge(
    'rag_db_connections',
    'Active database connections',
    ['pool']  # pool: core/ingest
)

# ============================================================================
# User Metrics
# ============================================================================

# User registrations
user_registrations = Counter(
    'rag_user_registrations_total',
    'User registrations',
    ['tier']
)

# User queries per tier
user_queries_by_tier = Counter(
    'rag_user_queries_by_tier_total',
    'User queries by tier',
    ['tier']
)

# Conversation metrics
conversations_total = Counter(
    'rag_conversations_total',
    'Total conversations',
    ['status']  # status: created/completed/abandoned
)

# Messages per conversation
messages_per_conversation = Histogram(
    'rag_messages_per_conversation',
    'Number of messages per conversation',
    buckets=[1, 2, 5, 10, 20, 50, 100]
)

# ============================================================================
# Feedback Metrics
# ============================================================================

# User feedback
user_feedback = Counter(
    'rag_user_feedback_total',
    'User feedback submissions',
    ['rating', 'feedback_type']
)

# Average feedback rating
average_feedback_rating = Gauge(
    'rag_average_feedback_rating',
    'Average user feedback rating'
)

# ============================================================================
# Sync Metrics
# ============================================================================

# Sync operations
sync_operations = Counter(
    'rag_sync_operations_total',
    'Sync operations from Ingest',
    ['status']  # status: success/error
)

# Synced embeddings
synced_embeddings = Counter(
    'rag_synced_embeddings_total',
    'Total embeddings synced from Ingest'
)

# Sync duration
sync_duration = Histogram(
    'rag_sync_duration_seconds',
    'Sync operation duration',
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0]
)

# ============================================================================
# System Metrics
# ============================================================================

# System info
system_info = Info(
    'rag_system',
    'RAG system information'
)

# API requests
api_requests = Counter(
    'rag_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

# API latency
api_latency = Histogram(
    'rag_api_latency_seconds',
    'API endpoint latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# ============================================================================
# Helper Functions
# ============================================================================

def record_query_metrics(
    status: str,
    user_tier: str,
    language: str,
    duration: float,
    tokens: int,
    model: str
):
    """
    Record metrics for a query.
    
    Args:
        status: Query status (success/error)
        user_tier: User tier
        language: Query language
        duration: Total duration in seconds
        tokens: Tokens used
        model: LLM model used
    """
    query_total.labels(
        status=status,
        user_tier=user_tier,
        language=language
    ).inc()
    
    query_duration.labels(stage='total').observe(duration)
    
    if tokens > 0:
        tokens_used.labels(
            model=model,
            user_tier=user_tier
        ).inc(tokens)


def record_cache_metrics(
    operation: str,
    layer: str,
    result: str
):
    """
    Record cache operation metrics.
    
    Args:
        operation: Operation type (get/set)
        layer: Cache layer (memory/redis/db)
        result: Operation result (hit/miss/success/error)
    """
    cache_operations.labels(
        operation=operation,
        layer=layer,
        result=result
    ).inc()


def record_rate_limit_violation(
    limit_type: str,
    user_tier: str
):
    """
    Record rate limit violation.
    
    Args:
        limit_type: Type of limit (minute/hour/day)
        user_tier: User tier
    """
    rate_limit_violations.labels(
        limit_type=limit_type,
        user_tier=user_tier
    ).inc()


def record_llm_metrics(
    provider: str,
    model: str,
    status: str,
    latency: float,
    error_type: str = None
):
    """
    Record LLM operation metrics.
    
    Args:
        provider: LLM provider (openai/groq/anthropic)
        model: Model name
        status: Request status (success/error)
        latency: Request latency in seconds
        error_type: Error type if status is error
    """
    llm_requests.labels(
        provider=provider,
        model=model,
        status=status
    ).inc()
    
    llm_latency.labels(
        provider=provider,
        model=model
    ).observe(latency)
    
    if error_type:
        llm_errors.labels(
            provider=provider,
            model=model,
            error_type=error_type
        ).inc()


def update_system_info(version: str, environment: str):
    """
    Update system information.
    
    Args:
        version: System version
        environment: Environment (development/staging/production)
    """
    system_info.info({
        'version': version,
        'environment': environment
    })
