"""
RAG Pipeline
Complete Retrieval-Augmented Generation pipeline
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import asyncio
import hashlib
from datetime import datetime, timedelta

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.qdrant_service import QdrantService
from app.services.local_embedding_service import get_local_embedding_service
from app.llm.openai_provider import OpenAIProvider
from app.llm.base import Message, LLMConfig
from app.core.dependencies import get_redis_client
from app.config.settings import settings

logger = structlog.get_logger()


@dataclass
class RAGQuery:
    """RAG query request."""
    text: str
    user_id: str
    conversation_id: Optional[str] = None
    language: str = "fa"
    max_chunks: int = 5
    filters: Optional[Dict[str, Any]] = None
    use_cache: bool = True
    use_reranking: bool = True


@dataclass
class RAGChunk:
    """Retrieved document chunk."""
    text: str
    score: float
    source: str
    metadata: Dict[str, Any]
    document_id: Optional[str] = None


@dataclass
class RAGResponse:
    """RAG pipeline response."""
    answer: str
    chunks: List[RAGChunk]
    sources: List[str]
    total_tokens: int
    processing_time_ms: int
    cached: bool = False
    model_used: str = ""


class RAGPipeline:
    """Complete RAG pipeline for question answering."""
    
    def __init__(self):
        """Initialize RAG pipeline components."""
        self.qdrant = QdrantService()
        self.embedder = get_local_embedding_service()  # Use local embedding
        self.llm = OpenAIProvider()
        self.reranker = None  # Will be initialized if needed
        
    async def process(self, query: RAGQuery) -> RAGResponse:
        """
        Process a query through the RAG pipeline.
        
        Args:
            query: RAG query request
            
        Returns:
            RAG response with answer and sources
        """
        start_time = datetime.utcnow()
        
        try:
            # Check cache if enabled
            if query.use_cache:
                cached_response = await self._check_cache(query)
                if cached_response:
                    cached_response.cached = True
                    return cached_response
            
            # Step 1: Query understanding and enhancement
            enhanced_query = await self._enhance_query(query)
            
            # Step 2: Generate embedding
            query_embedding = await self._generate_embedding(enhanced_query)
            
            # Step 3: Retrieve relevant chunks
            chunks = await self._retrieve_chunks(
                query_embedding,
                enhanced_query,
                query.filters,
                limit=query.max_chunks * 3  # Get more for reranking
            )
            
            # Step 4: Rerank if enabled
            if query.use_reranking and len(chunks) > query.max_chunks:
                chunks = await self._rerank_chunks(
                    enhanced_query,
                    chunks,
                    top_k=query.max_chunks
                )
            else:
                chunks = chunks[:query.max_chunks]
            
            # Step 5: Generate answer
            answer, tokens_used = await self._generate_answer(
                query.text,
                chunks,
                query.language,
                query.conversation_id
            )
            
            # Step 6: Extract sources
            sources = self._extract_sources(chunks)
            
            # Calculate processing time
            processing_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            # Create response
            response = RAGResponse(
                answer=answer,
                chunks=chunks,
                sources=sources,
                total_tokens=tokens_used,
                processing_time_ms=processing_time,
                model_used=self.llm.config.model
            )
            
            # Cache response if enabled
            if query.use_cache:
                await self._cache_response(query, response)
            
            return response
            
        except Exception as e:
            logger.error(f"RAG pipeline error: {e}")
            raise
    
    async def _enhance_query(self, query: RAGQuery) -> str:
        """
        Enhance query for better retrieval.
        
        Args:
            query: Original query
            
        Returns:
            Enhanced query text
        """
        # For Persian queries, we might want to:
        # 1. Fix common typos
        # 2. Expand abbreviations
        # 3. Add synonyms
        
        enhanced = query.text
        
        # Simple enhancement for now
        if query.language == "fa":
            # Persian-specific enhancements
            enhanced = enhanced.replace("ق.م", "قانون مدنی")
            enhanced = enhanced.replace("ق.ت", "قانون تجارت")
            enhanced = enhanced.replace("ق.آ.د.ک", "قانون آیین دادرسی کیفری")
        
        return enhanced
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text with retry logic.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # Local embedding is synchronous, wrap it in async
        import asyncio
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, 
            self.embedder.encode_single,
            text
        )
        return embedding.tolist()
    
    async def _retrieve_chunks(
        self,
        query_embedding: List[float],
        query_text: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[RAGChunk]:
        """
        Retrieve relevant chunks from vector database.
        
        Args:
            query_embedding: Query embedding vector
            query_text: Query text for hybrid search
            filters: Optional filters
            limit: Maximum chunks to retrieve
            
        Returns:
            List of relevant chunks
        """
        # Determine vector field based on embedding dimension
        vector_field = self._get_vector_field(len(query_embedding))
        
        # Perform hybrid search if enabled
        if settings.rag_use_hybrid_search:
            results = await self.qdrant.hybrid_search(
                query_vector=query_embedding,
                query_text=query_text,
                limit=limit,
                vector_weight=settings.rag_vector_weight,
                keyword_weight=settings.rag_bm25_weight,
                filters=filters,
                vector_field=vector_field
            )
        else:
            # Vector-only search
            results = await self.qdrant.search(
                query_vector=query_embedding,
                limit=limit,
                score_threshold=settings.rag_similarity_threshold,
                filters=filters,
                vector_field=vector_field
            )
        
        # Convert to RAGChunk objects
        chunks = []
        for result in results:
            chunk = RAGChunk(
                text=result["text"],
                score=result.get("score", 0.0),
                source=result.get("source", "unknown"),
                metadata=result.get("metadata", {}),
                document_id=result.get("document_id")
            )
            chunks.append(chunk)
        
        return chunks
    
    async def _rerank_chunks(
        self,
        query: str,
        chunks: List[RAGChunk],
        top_k: int
    ) -> List[RAGChunk]:
        """
        Rerank chunks for better relevance.
        
        Args:
            query: Query text
            chunks: Retrieved chunks
            top_k: Number of top chunks to return
            
        Returns:
            Reranked chunks
        """
        if not chunks:
            return []
        
        # If we have Cohere reranker configured
        if settings.cohere_api_key and self.reranker:
            try:
                reranked = await self.reranker.rerank(
                    query=query,
                    documents=[c.text for c in chunks],
                    top_k=top_k
                )
                
                # Reorder chunks based on reranking
                reranked_chunks = []
                for idx, score in reranked:
                    chunk = chunks[idx]
                    chunk.score = score  # Update score with rerank score
                    reranked_chunks.append(chunk)
                
                return reranked_chunks
                
            except Exception as e:
                logger.warning(f"Reranking failed, using original order: {e}")
        
        # Fallback: Simple score-based reranking
        # Combine original score with text similarity
        return sorted(chunks, key=lambda x: x.score, reverse=True)[:top_k]
    
    async def _generate_answer(
        self,
        query: str,
        chunks: List[RAGChunk],
        language: str,
        conversation_id: Optional[str]
    ) -> Tuple[str, int]:
        """
        Generate answer using LLM with retrieved context.
        
        Args:
            query: User query
            chunks: Retrieved chunks
            language: Response language
            conversation_id: Optional conversation ID for context
            
        Returns:
            Generated answer and tokens used
        """
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[منبع {i}]"
            if chunk.metadata.get("document_title"):
                source_info += f" {chunk.metadata['document_title']}"
            if chunk.metadata.get("unit_number"):
                source_info += f" - ماده {chunk.metadata['unit_number']}"
            
            context_parts.append(f"{source_info}:\n{chunk.text}")
        
        context = "\n\n".join(context_parts)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(language)
        
        # Build messages
        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user",
                content=f"""بر اساس اطلاعات زیر به سوال پاسخ دهید:

اطلاعات مرجع:
{context}

سوال: {query}

لطفاً پاسخی جامع و دقیق ارائه دهید و در صورت لزوم به منابع ارجاع دهید."""
            )
        ]
        
        # Add conversation history if available
        if conversation_id:
            # TODO: Load conversation history from database
            pass
        
        # Generate response
        response = await self.llm.generate(messages)
        
        return response.content, response.usage["total_tokens"]
    
    def _build_system_prompt(self, language: str) -> str:
        """Build system prompt based on language."""
        if language == "fa":
            return """شما یک دستیار حقوقی هوشمند هستید که به سوالات حقوقی بر اساس قوانین و مقررات ایران پاسخ می‌دهید.

وظایف شما:
1. پاسخ‌های دقیق و جامع بر اساس اطلاعات ارائه شده
2. ارجاع به منابع و مواد قانونی مرتبط
3. توضیح مفاهیم حقوقی به زبان ساده
4. اشاره به نکات مهم و استثناها

محدودیت‌ها:
- فقط بر اساس اطلاعات ارائه شده پاسخ دهید
- از اظهار نظر شخصی خودداری کنید
- در صورت عدم وجود اطلاعات کافی، صراحتاً اعلام کنید"""
        
        else:
            return """You are an intelligent legal assistant answering legal questions based on laws and regulations.

Your tasks:
1. Provide accurate and comprehensive answers based on provided information
2. Reference relevant legal sources and articles
3. Explain legal concepts in simple language
4. Highlight important points and exceptions

Limitations:
- Answer only based on provided information
- Avoid personal opinions
- Explicitly state if information is insufficient"""
    
    def _extract_sources(self, chunks: List[RAGChunk]) -> List[str]:
        """Extract unique sources from chunks."""
        sources = []
        seen = set()
        
        for chunk in chunks:
            # Build source string
            source_parts = []
            
            if chunk.metadata.get("document_title"):
                source_parts.append(chunk.metadata["document_title"])
            
            if chunk.metadata.get("unit_number"):
                source_parts.append(f"ماده {chunk.metadata['unit_number']}")
            
            if chunk.metadata.get("authority"):
                source_parts.append(f"({chunk.metadata['authority']})")
            
            source = " - ".join(source_parts) if source_parts else chunk.source
            
            if source and source not in seen:
                sources.append(source)
                seen.add(source)
        
        return sources
    
    def _get_vector_field(self, dim: int) -> str:
        """Get vector field name based on dimension."""
        if dim <= 512:
            return "small"
        elif dim <= 768:
            return "medium"
        elif dim <= 1536:
            return "large"
        else:
            return "default"
    
    async def _check_cache(self, query: RAGQuery) -> Optional[RAGResponse]:
        """
        Check if query result is cached.
        
        Args:
            query: Query to check
            
        Returns:
            Cached response if available
        """
        try:
            redis = await get_redis_client()
            
            # Generate cache key
            cache_key = self._generate_cache_key(query)
            
            # Check Redis cache
            cached = await redis.get(cache_key)
            if cached:
                import json
                data = json.loads(cached)
                
                # Reconstruct response
                chunks = [
                    RAGChunk(**chunk) for chunk in data["chunks"]
                ]
                
                return RAGResponse(
                    answer=data["answer"],
                    chunks=chunks,
                    sources=data["sources"],
                    total_tokens=data["total_tokens"],
                    processing_time_ms=data["processing_time_ms"],
                    cached=True,
                    model_used=data.get("model_used", "")
                )
            
            # TODO: Check database cache for semantic similarity
            
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
        
        return None
    
    async def _cache_response(
        self,
        query: RAGQuery,
        response: RAGResponse
    ):
        """
        Cache query response.
        
        Args:
            query: Original query
            response: Generated response
        """
        try:
            redis = await get_redis_client()
            
            # Generate cache key
            cache_key = self._generate_cache_key(query)
            
            # Prepare data for caching
            import json
            cache_data = {
                "answer": response.answer,
                "chunks": [
                    {
                        "text": c.text,
                        "score": c.score,
                        "source": c.source,
                        "metadata": c.metadata,
                        "document_id": c.document_id
                    }
                    for c in response.chunks
                ],
                "sources": response.sources,
                "total_tokens": response.total_tokens,
                "processing_time_ms": response.processing_time_ms,
                "model_used": response.model_used
            }
            
            # Cache in Redis with TTL
            await redis.setex(
                cache_key,
                settings.cache_ttl_query,
                json.dumps(cache_data, ensure_ascii=False)
            )
            
            # TODO: Also cache in database for semantic search
            
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def _generate_cache_key(self, query: RAGQuery) -> str:
        """Generate cache key for query."""
        # Create a unique key based on query parameters
        key_parts = [
            query.text.lower(),
            query.language,
            str(query.max_chunks),
            str(query.filters) if query.filters else "",
        ]
        
        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"rag:cache:{key_hash}"
