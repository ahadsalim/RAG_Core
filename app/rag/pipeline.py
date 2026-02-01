"""
RAG Pipeline
Complete Retrieval-Augmented Generation pipeline
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
import hashlib
import json
import re

import structlog
import pytz
import jdatetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.qdrant_service import QdrantService
from app.services.embedding_service import get_embedding_service
from app.services.reranker_service import get_reranker
from app.llm.base import Message
from app.llm.classifier import QueryClassifier
from app.llm.factory import create_llm2_pro
from app.core.dependencies import get_redis_client
from app.config.settings import settings
from app.config.prompts import (
    RAGPrompts,
    SystemPrompts,
    QueryEnhancementPrompts,
)

logger = structlog.get_logger()


@dataclass
class RAGQuery:
    """RAG query request."""
    text: str
    user_id: str
    conversation_id: Optional[str] = None
    language: str = "fa"
    max_chunks: int = None  # اگر None باشد از settings.rag_max_chunks استفاده می‌شود
    filters: Optional[Dict[str, Any]] = None
    use_cache: bool = True
    use_reranking: bool = True
    user_preferences: Optional[Dict[str, Any]] = None
    enable_web_search: bool = False
    # فیلتر زمانی برای قوانین
    temporal_context: Optional[str] = None  # "current" یا "past" یا None
    target_date: Optional[str] = None  # تاریخ هدف برای گذشته (YYYY-MM-DD)
    
    def __post_init__(self):
        """Set default values from settings if not provided."""
        if self.max_chunks is None:
            self.max_chunks = settings.rag_max_chunks


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
    input_tokens: int = 0
    output_tokens: int = 0
    reranker_details: Optional[List[Dict[str, Any]]] = None  # اطلاعات کامل reranker


class RAGPipeline:
    """Complete RAG pipeline for question answering."""
    
    def __init__(self):
        """Initialize RAG pipeline components."""
        self.qdrant = QdrantService()
        # Use unified embedding service (auto-detects API vs local)
        self.embedder = get_embedding_service()
        # استفاده از LLM2 (Pro) برای سوالات کسب‌وکار
        self.llm = create_llm2_pro()
        self.classifier = QueryClassifier()  # LLM برای دسته‌بندی سوالات
        self.reranker = get_reranker()  # Initialize Cohere reranker if configured
        if self.reranker:
            logger.info("RAG Pipeline initialized with LLM2 (Pro) and Cohere Reranker")
        else:
            logger.info("RAG Pipeline initialized with LLM2 (Pro) (no reranker)")
        
    async def process(
        self, 
        query: RAGQuery, 
        additional_context: str = None, 
        skip_classification: bool = False,
        image_urls: List[str] = None
    ) -> RAGResponse:
        """
        Process a query through the RAG pipeline.
        
        Args:
            query: RAG query request
            additional_context: Additional context for LLM (memory, file analysis, etc.)
            skip_classification: Skip classification if already done in query endpoint
            image_urls: List of presigned URLs for images to send to LLM
            
        Returns:
            RAG response with answer and sources
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 0: Classify query using LLM (if enabled and not skipped)
            # توجه: اگر از query.py آمده، classification قبلاً انجام شده و skip می‌شود
            classification = None
            if settings.enable_query_classification and not skip_classification:
                classification = await self.classifier.classify(query.text, query.language)
                
                logger.info(
                    "Query classified",
                    category=classification.category,
                    confidence=classification.confidence
                )
            
            # دسته‌بندی‌های مختلف:
            # 1. invalid_no_file, invalid_with_file → پاسخ مستقیم از کلاسیفیکیشن (direct_response)
            # 2. general → ارسال به LLM1 برای پاسخ عمومی (بدون RAG)
            # 3. business_no_file, business_with_file → ادامه به RAG
            
            invalid_categories = ["invalid_no_file", "invalid_with_file"]
            if classification and classification.category in invalid_categories:
                # پاسخ مستقیم برای سوالات نامعتبر
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                return RAGResponse(
                    answer=classification.direct_response or "لطفاً سوال خود را واضح‌تر بیان کنید.",
                    chunks=[],
                    sources=[],
                    total_tokens=0,
                    processing_time_ms=processing_time,
                    cached=False,
                    model_used="classifier"
                )
            
            if classification and classification.category == "general":
                # سوالات عمومی → ارسال به LLM1 بدون RAG
                processing_time_start = datetime.utcnow()
                try:
                    llm_response = await self._generate_general_response(query.text)
                    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    return RAGResponse(
                        answer=llm_response,
                        chunks=[],
                        sources=[],
                        total_tokens=0,
                        processing_time_ms=processing_time,
                        cached=False,
                        model_used="llm1_general"
                    )
                except Exception as e:
                    logger.error(f"Error generating general response: {e}")
                    # در صورت خطا، ادامه به RAG
                    pass
            
            # فقط برای سوالات واقعی ادامه می‌دهیم
            
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
            # استفاده از ضریب تنظیم‌شده در settings برای تعداد chunks اولیه
            retrieve_limit = query.max_chunks * settings.rag_retrieve_multiplier
            chunks = await self._retrieve_chunks(
                query_embedding,
                enhanced_query,
                query.filters,
                limit=retrieve_limit
            )
            
            logger.info(
                "Retrieved chunks",
                query=query.text[:100],
                enhanced_query=enhanced_query[:100],
                num_chunks=len(chunks),
                top_scores=[c.score for c in chunks[:3]] if chunks else []
            )
            
            # Step 3.5: فیلتر بر اساس تاریخ اعتبار قوانین
            if query.temporal_context:
                chunks = self._filter_chunks_by_validity(
                    chunks,
                    query.temporal_context,
                    query.target_date
                )
            
            # Step 4: Rerank if enabled
            reranker_details = []
            if query.use_reranking and len(chunks) > query.max_chunks:
                chunks, reranker_details = await self._rerank_chunks(
                    enhanced_query,
                    chunks,
                    top_k=query.max_chunks
                )
                logger.info(
                    "Reranked chunks",
                    final_count=len(chunks),
                    top_scores=[c.score for c in chunks[:3]] if chunks else []
                )
            else:
                chunks = chunks[:query.max_chunks]
                logger.info(
                    "Using top chunks without reranking",
                    count=len(chunks)
                )
            
            # Step 4.5: Expand legal context for lunit nodes
            chunks = await self._expand_legal_context(chunks)
            logger.info(
                "Context expansion completed",
                final_count=len(chunks)
            )
            
            # Step 5: Generate answer
            logger.info(
                "Generating answer",
                num_chunks=len(chunks),
                chunk_sources=[c.metadata.get('work_title', 'N/A')[:50] for c in chunks[:3]]
            )
            
            answer, tokens_used, input_tokens, output_tokens = await self._generate_answer(
                query.text,
                chunks,
                query.language,
                query.conversation_id,
                query.user_preferences,
                additional_context=additional_context,
                enable_web_search=query.enable_web_search,
                image_urls=image_urls
            )
            
            # Step 6: Extract sources (filter based on LLM's decision)
            # اگر LLM تشخیص داد که قانون/ماده وجود ندارد، منابع نمایش داده نشوند
            if answer.startswith("[NO_SOURCES]"):
                # حذف تگ از پاسخ و خالی کردن منابع
                answer = answer.replace("[NO_SOURCES]", "").strip()
                sources = []
                chunks = []
                logger.info("LLM indicated no sources should be shown (non-existent law/article)")
            else:
                # استخراج منابع استفاده شده توسط LLM
                answer, used_source_indices = self._extract_used_sources(answer)
                
                if used_source_indices is not None:
                    if len(used_source_indices) == 0:
                        # LLM گفته هیچ منبعی استفاده نشده
                        chunks = []
                        sources = []
                        logger.info("LLM indicated no sources were used")
                    else:
                        # فیلتر chunks بر اساس منابع استفاده شده
                        filtered_chunks = []
                        for idx in used_source_indices:
                            if 0 < idx <= len(chunks):
                                filtered_chunks.append(chunks[idx - 1])  # تبدیل 1-indexed به 0-indexed
                        
                        logger.info(
                            "Filtered sources based on LLM decision",
                            original_count=len(chunks),
                            used_indices=used_source_indices,
                            filtered_count=len(filtered_chunks)
                        )
                        chunks = filtered_chunks
                        sources = self._extract_sources(chunks)
                else:
                    # اگر LLM تگ را ننوشت، همه منابع را نگه می‌داریم (backward compatibility)
                    sources = self._extract_sources(chunks)
                    logger.warning("LLM did not specify used sources, keeping all")
            
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
                model_used=self.llm.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reranker_details=reranker_details
            )
            
            # Cache response if enabled
            if query.use_cache:
                await self._cache_response(query, response)
            
            return response
            
        except Exception as e:
            logger.error(f"RAG pipeline error: {e}")
            raise
    
    async def _generate_general_response(self, query_text: str) -> str:
        """تولید پاسخ برای سوالات عمومی (غیر تخصصی) بدون RAG."""
        system_prompt = SystemPrompts.get_general_question_prompt()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=query_text)
        ]
        
        response = await self.llm.generate_responses_api(
            messages=messages, reasoning_effort="low", max_tokens=500
        )
        return response.content
    
    async def _enhance_query(self, query: RAGQuery) -> str:
        """
        Enhance query for better retrieval using LLM.
        
        Args:
            query: Original query
            
        Returns:
            Enhanced query text
        """
        if query.language != "fa":
            return query.text
        
        try:
            system_prompt = QueryEnhancementPrompts.get_enhancement_prompt(query.language)
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=f"سوال کاربر: {query.text}")
            ]
            
            response = await self.llm.generate_responses_api(
                messages, reasoning_effort="low", max_tokens=200
            )
            
            enhanced = response.content.strip()
            
            # اگر LLM چیز عجیبی برگرداند، از query اصلی استفاده کن
            if not enhanced or len(enhanced) > len(query.text) * 3:
                logger.warning("LLM enhancement failed, using original query")
                return query.text
            
            logger.info(f"Query enhanced: '{query.text}' -> '{enhanced}'")
            return enhanced
            
        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}")
            return query.text
    
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
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, self.embedder.encode_single, text
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
        
        logger.debug(
            "Retrieved chunks from Qdrant",
            count=len(chunks),
            vector_field=vector_field,
            top_3_docs=[c.metadata.get('work_title', 'N/A')[:30] for c in chunks[:3]]
        )
        
        return chunks
    
    def _filter_chunks_by_validity(
        self,
        chunks: List[RAGChunk],
        temporal_context: Optional[str],
        target_date: Optional[str]
    ) -> List[RAGChunk]:
        """
        فیلتر chunks بر اساس تاریخ اعتبار قوانین.
        
        Args:
            chunks: لیست chunks
            temporal_context: "current" (قوانین معتبر امروز) یا "past" (قوانین معتبر در تاریخ هدف)
            target_date: تاریخ هدف برای گذشته (YYYY-MM-DD)
            
        Returns:
            chunks فیلتر شده
        """
        if not temporal_context:
            return chunks
        
        # تعیین تاریخ مرجع
        if temporal_context == "current":
            reference_date = datetime.utcnow().date()
        elif temporal_context == "past" and target_date:
            try:
                reference_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Invalid target_date format: {target_date}, using current date")
                reference_date = datetime.utcnow().date()
        else:
            return chunks
        
        filtered_chunks = []
        excluded_count = 0
        
        for chunk in chunks:
            metadata = chunk.metadata
            
            # بررسی is_active (اولویت اول)
            is_active = metadata.get("is_active")
            
            # برای سوالات "current": اگر is_active=False، حذف کن
            if temporal_context == "current" and is_active is False:
                excluded_count += 1
                logger.debug(
                    "Excluded chunk: is_active=False",
                    work_title=metadata.get("work_title", "")[:30]
                )
                continue
            
            # بررسی valid_from و valid_to
            valid_from_str = metadata.get("valid_from")
            valid_to_str = metadata.get("valid_to")
            
            # اگر فیلد تاریخ اعتبار نداشت، نگه می‌داریم
            if not valid_from_str:
                filtered_chunks.append(chunk)
                continue
            
            try:
                # پارس تاریخ‌ها
                valid_from = datetime.strptime(valid_from_str[:10], "%Y-%m-%d").date()
                valid_to = None
                if valid_to_str:
                    valid_to = datetime.strptime(valid_to_str[:10], "%Y-%m-%d").date()
                
                # بررسی اعتبار در تاریخ مرجع
                # قانون معتبر است اگر: valid_from <= reference_date AND (valid_to is None OR valid_to > reference_date)
                is_valid = valid_from <= reference_date
                if valid_to:
                    is_valid = is_valid and valid_to > reference_date
                
                if is_valid:
                    filtered_chunks.append(chunk)
                else:
                    excluded_count += 1
                    logger.debug(
                        "Excluded chunk due to validity",
                        work_title=metadata.get("work_title", "")[:30],
                        valid_from=valid_from_str,
                        valid_to=valid_to_str,
                        reference_date=str(reference_date)
                    )
            except (ValueError, TypeError) as e:
                # اگر پارس تاریخ خطا داد، نگه می‌داریم
                filtered_chunks.append(chunk)
        
        if excluded_count > 0:
            logger.info(
                "Filtered chunks by validity date",
                temporal_context=temporal_context,
                reference_date=str(reference_date),
                original_count=len(chunks),
                filtered_count=len(filtered_chunks),
                excluded_count=excluded_count
            )
        
        return filtered_chunks
    
    async def _rerank_chunks(
        self,
        query: str,
        chunks: List[RAGChunk],
        top_k: int
    ) -> Tuple[List[RAGChunk], List[Dict[str, Any]]]:
        """
        Rerank chunks for better relevance.
        
        Args:
            query: Query text
            chunks: Retrieved chunks
            top_k: Number of top chunks to return
            
        Returns:
            Tuple of (reranked_chunks, reranker_details)
            reranker_details contains full info about all chunks before filtering
        """
        reranker_details = []
        
        if not chunks:
            return [], []
        
        # If we have reranker configured (local Docker service or Cohere API)
        if self.reranker:
            try:
                # درخواست همه نتایج برای دیدن امتیازات کامل
                reranked = await self.reranker.rerank(
                    query=query,
                    documents=[c.text for c in chunks],
                    top_k=len(chunks)  # همه را بگیر
                )
                
                # ذخیره اطلاعات کامل همه chunks
                for idx, score in reranked:
                    chunk = chunks[idx]
                    reranker_details.append({
                        "original_index": idx,
                        "score": round(score, 4),
                        "source": chunk.metadata.get("work_title", "")[:50],
                        "unit": chunk.metadata.get("unit_number", ""),
                        "text_preview": chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text
                    })
                
                # Reorder chunks based on reranking - فقط top_k با اعمال threshold
                threshold = settings.rag_reranker_threshold
                reranked_chunks = []
                for idx, score in reranked[:top_k]:
                    # اگر threshold تنظیم شده، chunks با امتیاز کمتر را حذف کن
                    if threshold > 0 and score < threshold:
                        continue
                    chunk = chunks[idx]
                    chunk.score = score  # Update score with rerank score
                    reranked_chunks.append(chunk)
                
                logger.info(
                    "Reranking completed",
                    original_count=len(chunks),
                    reranked_count=len(reranked_chunks),
                    threshold=threshold,
                    filtered_by_threshold=top_k - len(reranked_chunks),
                    all_scores=[d["score"] for d in reranker_details],
                    top_scores=[c.score for c in reranked_chunks[:3]]
                )
                
                return reranked_chunks, reranker_details
                
            except Exception as e:
                logger.warning(f"Reranking failed, using original order: {e}")
        
        # Fallback: Simple score-based reranking
        sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)[:top_k]
        return sorted_chunks, []
    
    async def _expand_legal_context(self, chunks: List[RAGChunk]) -> List[RAGChunk]:
        """
        توسعه context برای نودهای lunit (مواد حقوقی).
        اگر chunk یک بخش از یک ماده حقوقی است، تمام بخش‌های آن ماده را بازیابی و اضافه می‌کند.
        
        فقط برای document_type="lunit" کار می‌کند.
        برای qaentry و textentry هیچ کاری انجام نمی‌شود.
        
        Args:
            chunks: لیست chunks بازیابی شده
            
        Returns:
            chunks با context توسعه یافته
        """
        if not chunks:
            return chunks
        
        expanded_chunks = []
        seen_articles = set()  # برای جلوگیری از تکرار: (document_id, unit_number)
        expansion_count = 0
        
        for chunk in chunks:
            metadata = chunk.metadata
            
            # فقط برای lunit nodes
            doc_type = metadata.get("document_type", "")
            if doc_type != "lunit":
                # qaentry و textentry را بدون تغییر اضافه کن
                expanded_chunks.append(chunk)
                continue
            
            # استخراج اطلاعات ماده
            document_id = metadata.get("document_id")
            unit_number = metadata.get("unit_number")
            
            if not document_id or not unit_number:
                # اگر اطلاعات کامل نیست، همان chunk را اضافه کن
                expanded_chunks.append(chunk)
                continue
            
            # کلید یکتا برای این ماده
            article_key = f"{document_id}_{unit_number}"
            
            if article_key in seen_articles:
                # این ماده قبلاً پردازش شده، رد شو
                continue
            
            seen_articles.add(article_key)
            
            # بازیابی تمام chunks مربوط به این ماده از Qdrant
            try:
                # استفاده از scroll برای بازیابی تمام chunks با فیلتر
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                
                scroll_filter = Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        ),
                        FieldCondition(
                            key="unit_number",
                            match=MatchValue(value=unit_number)
                        )
                    ]
                )
                
                # Scroll through all matching points
                scroll_result = self.qdrant.client.scroll(
                    collection_name=self.qdrant.collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,  # حداکثر تعداد chunks برای یک ماده
                    with_payload=True,
                    with_vectors=False
                )
                
                article_points = scroll_result[0]  # لیست points
                
                if not article_points:
                    # اگر چیزی پیدا نشد، همان chunk اصلی را اضافه کن
                    expanded_chunks.append(chunk)
                    continue
                
                # تبدیل points به RAGChunk و مرتب‌سازی بر اساس chunk_index
                article_chunks = []
                for point in article_points:
                    payload = point.payload
                    article_chunks.append(RAGChunk(
                        text=payload.get("text", ""),
                        score=chunk.score,  # همان score chunk اصلی
                        source=payload.get("source", ""),
                        metadata=payload,
                        document_id=payload.get("document_id")
                    ))
                
                # مرتب‌سازی بر اساس chunk_index
                article_chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
                
                # اضافه کردن به لیست نهایی
                expanded_chunks.extend(article_chunks)
                expansion_count += len(article_chunks) - 1  # تعداد chunks اضافه شده
                
                logger.debug(
                    "Expanded legal article",
                    document_id=document_id,
                    unit_number=unit_number,
                    work_title=metadata.get("work_title", "")[:50],
                    chunks_added=len(article_chunks)
                )
                
            except Exception as e:
                logger.warning(
                    f"Failed to expand legal context for article {unit_number}: {e}",
                    document_id=document_id,
                    unit_number=unit_number
                )
                # در صورت خطا، همان chunk اصلی را اضافه کن
                expanded_chunks.append(chunk)
        
        if expansion_count > 0:
            logger.info(
                "Legal context expansion completed",
                original_chunks=len(chunks),
                expanded_chunks=len(expanded_chunks),
                additional_chunks=expansion_count,
                articles_expanded=len(seen_articles)
            )
        
        return expanded_chunks
    
    async def _generate_answer(
        self,
        query: str,
        chunks: List[RAGChunk],
        language: str,
        conversation_id: Optional[str],
        user_preferences: Optional[Dict[str, Any]] = None,
        additional_context: str = None,
        enable_web_search: bool = False,
        image_urls: List[str] = None
    ) -> Tuple[str, int, int, int]:
        """
        Generate answer using LLM with retrieved context.
        
        Args:
            query: User query
            chunks: Retrieved chunks
            language: Response language
            conversation_id: Optional conversation ID for context
            user_preferences: Optional user preferences for response customization
            additional_context: Additional context (memory, file analysis, etc.)
            enable_web_search: Enable web search to supplement RAG sources
            image_urls: List of presigned URLs for images to send to LLM
            
        Returns:
            Tuple of (answer, total_tokens, input_tokens, output_tokens)
        """
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[منبع {i}]"
            work_title = chunk.metadata.get("work_title") or chunk.metadata.get("document_title")
            if work_title:
                source_info += f" {work_title}"
            if chunk.metadata.get("unit_number"):
                source_info += f" - ماده {chunk.metadata['unit_number']}"
            
            context_parts.append(f"{source_info}:\n{chunk.text}")
        
        context = "\n\n".join(context_parts)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(language, user_preferences)
        
        # Build user message
        if language == "fa":
            user_message_parts = []
            
            # اضافه کردن additional context (حافظه، فایل، و...)
            if additional_context:
                user_message_parts.append(additional_context)
                user_message_parts.append("\n" + "="*50 + "\n")
            else:
                # اگر additional_context نیست، سوال کاربر را مستقیم اضافه کن
                user_message_parts.append(f"[سوال فعلی]\n{query}\n")
            
            user_message_parts.append(f"""اطلاعات مرجع از پایگاه داده:
{context}""")
            
            user_message = "\n".join(user_message_parts)
        else:
            user_message_parts = []
            
            if additional_context:
                user_message_parts.append(additional_context)
                user_message_parts.append("\n" + "="*50 + "\n")
            else:
                # If no additional_context, add user query directly
                user_message_parts.append(f"[Current Question]\n{query}\n")
            
            user_message_parts.append(f"""Reference information from database:
{context}""")
            
            user_message = "\n".join(user_message_parts)
        
        # Add user preferences to the message if provided
        if user_preferences:
            prefs_text = self._format_user_preferences(user_preferences, language)
            if prefs_text:
                user_message += f"\n\n{prefs_text}"
        
        # Build messages
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message)
        ]
        
        # Generate response - با یا بدون web search و تصاویر
        if image_urls:
            # اگر تصویر داریم، از input_content با input_image استفاده کن
            content_parts = [
                {"type": "input_text", "text": f"{system_prompt}\n\n---\n\n{user_message}"}
            ]
            for img_url in image_urls:
                content_parts.append({
                    "type": "input_image",
                    "image_url": img_url
                })
            
            input_content = [{"role": "user", "content": content_parts}]
            
            logger.info(f"Generating RAG answer with {len(image_urls)} images")
            response = await self.llm.generate_responses_api(
                messages=[],
                reasoning_effort="medium",
                input_content=input_content
            )
        elif enable_web_search:
            logger.info("Generating RAG answer with web search enabled")
            response = await self.llm.generate_with_web_search(messages)
        else:
            response = await self.llm.generate_responses_api(
                messages,
                reasoning_effort="medium"
            )
        
        # برگرداندن توکن‌های ورودی و خروجی به صورت جداگانه
        input_tokens = response.usage.get("prompt_tokens", 0)
        output_tokens = response.usage.get("completion_tokens", 0)
        total_tokens = response.usage.get("total_tokens", input_tokens + output_tokens)
        
        return response.content, total_tokens, input_tokens, output_tokens
    
    def _build_system_prompt(self, language: str, user_preferences: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt based on language and user preferences."""
        # Get current date and time in Tehran timezone
        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
        
        current_date_shamsi = jalali_now.strftime('%Y/%m/%d')
        current_time = now.strftime('%H:%M')
        
        if language == "fa":
            base_prompt = RAGPrompts.get_rag_system_prompt_fa(
                current_date_shamsi=current_date_shamsi,
                current_time_fa=current_time
            )
        else:
            base_prompt = RAGPrompts.get_rag_system_prompt_en(
                current_date_gregorian=now.strftime('%Y-%m-%d'),
                current_date_shamsi=current_date_shamsi,
                current_time=current_time
            )
        
        # Add user preferences if provided
        if user_preferences:
            base_prompt += self._format_preferences_for_prompt(user_preferences, language)
        
        return base_prompt
    
    def _format_preferences_for_prompt(self, prefs: Dict[str, Any], language: str) -> str:
        """Format user preferences for system prompt."""
        additions = []
        
        if prefs.get("response_style"):
            key = "سبک پاسخ" if language == "fa" else "Response style"
            additions.append(f"- {key}: {prefs['response_style']}")
        
        if prefs.get("detail_level"):
            key = "سطح جزئیات" if language == "fa" else "Detail level"
            additions.append(f"- {key}: {prefs['detail_level']}")
        
        if not additions:
            return ""
        
        header = "\n\nترجیحات کاربر:\n" if language == "fa" else "\n\nUser preferences:\n"
        return header + "\n".join(additions)
    
    def _format_user_preferences(self, preferences: Dict[str, Any], language: str) -> str:
        """Format user preferences into a readable instruction for LLM."""
        if not preferences:
            return ""
        
        # Translation maps for Persian
        STYLE_MAP_FA = {
            "formal": "رسمی و تخصصی", "casual": "غیررسمی و ساده",
            "academic": "آکادمیک و علمی", "simple": "ساده و قابل فهم"
        }
        LEVEL_MAP_FA = {
            "brief": "خلاصه و مختصر", "moderate": "متوسط",
            "comprehensive": "جامع و کامل", "detailed": "با جزئیات کامل"
        }
        FORMAT_MAP_FA = {
            "bullet_points": "پاسخ را به صورت نکات کلیدی ارائه دهید",
            "numbered_list": "پاسخ را به صورت لیست شماره‌دار ارائه دهید",
            "paragraph": "پاسخ را به صورت پاراگراف‌های منسجم ارائه دهید"
        }
        
        instructions = []
        is_fa = language == "fa"
        
        if preferences.get("response_style"):
            val = preferences["response_style"]
            label = STYLE_MAP_FA.get(val, val) if is_fa else val
            instructions.append(f"{'سبک پاسخ' if is_fa else 'Response style'}: {label}")
        
        if preferences.get("detail_level"):
            val = preferences["detail_level"]
            label = LEVEL_MAP_FA.get(val, val) if is_fa else val
            instructions.append(f"{'سطح جزئیات' if is_fa else 'Detail level'}: {label}")
        
        if preferences.get("include_examples"):
            instructions.append("لطفاً مثال‌های عملی ارائه دهید" if is_fa else "Please include practical examples")
        
        if preferences.get("format"):
            val = preferences["format"]
            label = FORMAT_MAP_FA.get(val, val) if is_fa else val
            instructions.append(label if is_fa else f"Format: {label}")
        
        if not instructions:
            return ""
        
        header = "راهنمای پاسخ:\n" if is_fa else "Response guidelines:\n"
        return header + "\n".join(f"- {inst}" for inst in instructions)
    
    def _extract_sources(self, chunks: List[RAGChunk]) -> List[str]:
        """Extract detailed sources from chunks with full context."""
        sources = []
        seen = set()
        source_number = 0  # شماره‌گذاری صحیح منابع
        
        for chunk in chunks:
            metadata = chunk.metadata
            
            # جلوگیری از تکرار بر اساس document_id + unit_number
            source_key = f"{metadata.get('document_id', '')}_{metadata.get('unit_number', '')}"
            if source_key in seen:
                continue  # این chunk تکراری است، رد شو
            seen.add(source_key)
            
            # افزایش شماره منبع فقط برای منابع غیرتکراری
            source_number += 1
            source_lines = []
            
            # 1. شماره منبع و متن کامل
            source_lines.append(f"📌 منبع {source_number}:")
            source_lines.append(f"📄 متن: {chunk.text}")
            source_lines.append("")  # خط خالی
            
            # 2. نام قانون/سند و نوع
            doc_type = metadata.get("document_type") or metadata.get("doc_type", "")
            doc_title = metadata.get("document_title", "")
            unit_type = metadata.get("unit_type", "")
            
            # استفاده از work_title به جای document_title
            work_title = metadata.get("work_title", "")
            if not work_title:
                work_title = doc_title
            
            if work_title:
                source_lines.append(f"📚 نام سند: {work_title}")
                if doc_type and doc_type != work_title:
                    source_lines.append(f"📋 نوع: {doc_type}")
            
            # 3. مسیر دقیق (از path_label یا ساخت دستی)
            path_label = metadata.get("path_label", "")
            
            if path_label:
                # استفاده از مسیر کامل از metadata
                source_lines.append(f"📍 مسیر: {path_label}")
            else:
                # ساخت مسیر از فیلدهای جداگانه
                unit_number = metadata.get("unit_number")
                title = metadata.get("title", "")
                
                if unit_number:
                    if unit_type == "article":
                        source_lines.append(f"📍 ماده {unit_number}")
                    elif unit_type:
                        source_lines.append(f"📍 {unit_type} {unit_number}")
                    else:
                        source_lines.append(f"📍 ماده {unit_number}")
                
                if title and title != work_title:
                    source_lines.append(f"   عنوان: {title}")
            
            # 4. مرجع تصویب (فقط برای غیر قوانین)
            authority = metadata.get("authority", "")
            
            # تشخیص نوع سند - اگر قانون است، مرجع تصویب نمایش نده
            is_law = work_title and ("قانون" in work_title.lower())
            
            # فقط برای بخشنامه/آیین‌نامه/رای مرجع تصویب نمایش داده می‌شود
            if authority and not is_law:
                source_lines.append(f"✅ مرجع تصویب: {authority}")
            
            # ساخت source نهایی
            source = "\n".join(source_lines)
            sources.append(source)
        
        return sources
    
    def _extract_used_sources(self, answer: str) -> Tuple[str, Optional[List[int]]]:
        """استخراج شماره منابع استفاده شده از پاسخ LLM."""
        # الگوی جستجو برای تگ USED_SOURCES
        pattern = r'\[USED_SOURCES:\s*([^\]]+)\]'
        match = re.search(pattern, answer, re.IGNORECASE)
        
        if not match:
            return answer, None
        
        # حذف تگ از پاسخ
        cleaned_answer = re.sub(pattern, '', answer, flags=re.IGNORECASE).strip()
        
        # استخراج محتوای تگ
        content = match.group(1).strip().upper()
        
        if content == 'NONE':
            return cleaned_answer, []
        
        # استخراج اعداد
        try:
            indices = [int(x.strip()) for x in content.split(',') if x.strip().isdigit()]
            return cleaned_answer, indices
        except ValueError:
            logger.warning(f"Could not parse USED_SOURCES content: {content}")
            return cleaned_answer, None
    
    def _get_vector_field(self, dim: int) -> str:
        """Get vector field name based on dimension."""
        if dim <= 512:
            return "small"
        elif dim <= 768:
            return "medium"
        elif dim <= 1024:
            return "large"  # e5-large, bge-m3
        elif dim <= 1536:
            return "xlarge"  # OpenAI ada-002, text-embedding-3-small
        else:
            return "default"  # 3072
    
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
                    model_used=data.get("model_used", ""),
                    input_tokens=data.get("input_tokens", 0),
                    output_tokens=data.get("output_tokens", 0)
                )
            
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
                "model_used": response.model_used,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens
            }
            
            # Cache in Redis with TTL
            await redis.setex(
                cache_key,
                settings.cache_ttl_query,
                json.dumps(cache_data, ensure_ascii=False)
            )
            
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
