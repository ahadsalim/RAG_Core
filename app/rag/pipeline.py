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
from app.services.embedding_service import get_embedding_service  # Unified embedding service
from app.llm.openai_provider import OpenAIProvider
from app.llm.base import Message, LLMConfig
from app.llm.classifier import QueryClassifier
from app.llm.factory import create_llm2_pro  # LLM2 (Pro) برای سوالات کسب‌وکار
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
    user_preferences: Optional[Dict[str, Any]] = None


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
        # Use unified embedding service (auto-detects API vs local)
        self.embedder = get_embedding_service()
        # استفاده از LLM2 (Pro) برای سوالات کسب‌وکار
        self.llm = create_llm2_pro()
        self.classifier = QueryClassifier()  # LLM برای دسته‌بندی سوالات
        self.reranker = None  # Will be initialized if needed
        logger.info("RAG Pipeline initialized with LLM2 (Pro)")
        
    async def process(self, query: RAGQuery, additional_context: str = None) -> RAGResponse:
        """
        Process a query through the RAG pipeline.
        
        Args:
            query: RAG query request
            additional_context: Additional context for LLM (memory, file analysis, etc.)
            
        Returns:
            RAG response with answer and sources
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 0: Classify query using LLM (if enabled)
            classification = None
            if settings.enable_query_classification:
                classification = await self.classifier.classify(query.text, query.language)
                
                logger.info(
                    "Query classified",
                    category=classification.category,
                    confidence=classification.confidence
                )
            
            # اگر سوال احوالپرسی، چرت‌وپرت، یا نامعتبر بود → پاسخ مستقیم
            if classification and classification.category != "business_question":
                processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return RAGResponse(
                    answer=classification.direct_response or "متاسفانه نمی‌توانم به این سوال پاسخ دهم.",
                    chunks=[],
                    sources=[],
                    total_tokens=0,
                    processing_time_ms=processing_time,
                    cached=False,
                    model_used=self.classifier.llm_config.model
                )
            
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
            chunks = await self._retrieve_chunks(
                query_embedding,
                enhanced_query,
                query.filters,
                limit=query.max_chunks * 3  # Get more for reranking
            )
            
            logger.info(
                "Retrieved chunks",
                query=query.text[:100],
                enhanced_query=enhanced_query[:100],
                num_chunks=len(chunks),
                top_scores=[c.score for c in chunks[:3]] if chunks else []
            )
            
            # Step 4: Rerank if enabled
            if query.use_reranking and len(chunks) > query.max_chunks:
                chunks = await self._rerank_chunks(
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
            
            # Step 5: Generate answer
            logger.info(
                "Generating answer",
                num_chunks=len(chunks),
                chunk_sources=[c.metadata.get('work_title', 'N/A')[:50] for c in chunks[:3]]
            )
            
            answer, tokens_used = await self._generate_answer(
                query.text,
                chunks,
                query.language,
                query.conversation_id,
                query.user_preferences,
                additional_context=additional_context
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
        Enhance query for better retrieval using LLM.
        
        Args:
            query: Original query
            
        Returns:
            Enhanced query text
        """
        # استفاده از LLM برای بهبود query
        try:
            if query.language == "fa":
                system_prompt = """شما یک متخصص جستجوی اسناد حقوقی هستید.
وظیفه شما: سوال کاربر را دریافت کرده و آن را برای جستجو در پایگاه داده بهینه کنید.

کارهایی که باید انجام دهید:
1. اختصارات قوانین را باز کنید (مثل ق.م → قانون مدنی، ق.ت.ا → قانون تأمین اجتماعی)
2. اعداد فارسی را به انگلیسی تبدیل کنید (۱۲۳ → 123)
3. اعداد کلامی را به عددی تبدیل کنید (ده → 10، بیست و پنج → 25)
4. املای اشتباه را تصحیح کنید
5. کلمات مترادف مهم اضافه کنید (در صورت نیاز)

مهم: فقط query بهینه شده را برگردانید، بدون توضیح اضافی.

مثال 1:
ورودی: "ق.م ماده ۱۷۹"
خروجی: "قانون مدنی ماده 179"

مثال 2:
ورودی: "ماده ده قانون چلمنگان"
خروجی: "ماده 10 قانون چلمنگان"

مثال 3:
ورودی: "ق.ت.ا در مورد بازنشستگی"
خروجی: "قانون تأمین اجتماعی بازنشستگی"

فقط query بهینه شده را برگردانید."""

                user_message = f"سوال کاربر: {query.text}"
                
                messages = [
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_message)
                ]
                
                # استفاده از LLM سبک‌تر برای enhancement
                response = await self.llm.generate(
                    messages,
                    temperature=0.1,  # کم برای consistency
                    max_tokens=200
                )
                
                enhanced = response.content.strip()
                
                # اگر LLM چیز عجیبی برگرداند، از query اصلی استفاده کن
                if not enhanced or len(enhanced) > len(query.text) * 3:
                    enhanced = query.text
                    logger.warning("LLM enhancement failed, using original query")
                
                logger.info(f"Query enhanced via LLM: '{query.text}' -> '{enhanced}'")
                return enhanced
                
            else:
                # برای زبان‌های دیگر فعلاً enhancement نداریم
                return query.text
                
        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}, using original query")
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
        
        logger.debug(
            "Retrieved chunks from Qdrant",
            count=len(chunks),
            vector_field=vector_field,
            top_3_docs=[c.metadata.get('work_title', 'N/A')[:30] for c in chunks[:3]]
        )
        
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
        conversation_id: Optional[str],
        user_preferences: Optional[Dict[str, Any]] = None,
        additional_context: str = None
    ) -> Tuple[str, int]:
        """
        Generate answer using LLM with retrieved context.
        
        Args:
            query: User query
            chunks: Retrieved chunks
            language: Response language
            conversation_id: Optional conversation ID for context
            user_preferences: Optional user preferences for response customization
            additional_context: Additional context (memory, file analysis, etc.)
            
        Returns:
            Generated answer and tokens used
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
            
            user_message_parts.append(f"""اطلاعات مرجع از پایگاه داده:
{context}""")
            
            user_message = "\n".join(user_message_parts)
        else:
            user_message_parts = []
            
            if additional_context:
                user_message_parts.append(additional_context)
                user_message_parts.append("\n" + "="*50 + "\n")
            
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
        
        # Add conversation history if available
        if conversation_id:
            # TODO: Load conversation history from database
            pass
        
        # Generate response
        response = await self.llm.generate(messages)
        
        return response.content, response.usage["total_tokens"]
    
    def _build_system_prompt(self, language: str, user_preferences: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt based on language and user preferences."""
        from datetime import datetime
        import pytz
        import jdatetime
        from app.config.prompts import RAGPrompts
        
        # Get current date and time in Tehran timezone
        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        
        # Convert to Jalali (Shamsi) calendar
        jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
        current_date_shamsi = jalali_now.strftime('%Y/%m/%d')  # 1404/09/10
        current_time_fa = now.strftime('%H:%M')     # 16:24
        
        if language == "fa":
            base_prompt = RAGPrompts.get_rag_system_prompt_fa(
                current_date_shamsi=current_date_shamsi,
                current_time_fa=current_time_fa
            )
        else:
            # English prompt
            current_date_gregorian = now.strftime('%Y-%m-%d')
            current_time_en = now.strftime('%H:%M')
            
            base_prompt = RAGPrompts.get_rag_system_prompt_en(
                current_date_gregorian=current_date_gregorian,
                current_date_shamsi=current_date_shamsi,
                current_time=current_time_en
            )
        
        # Add user preferences to system prompt if provided
        if user_preferences:
            pref_additions = []
            
            if user_preferences.get("response_style"):
                style = user_preferences["response_style"]
                if language == "fa":
                    pref_additions.append(f"- سبک پاسخ: {style}")
                else:
                    pref_additions.append(f"- Response style: {style}")
            
            if user_preferences.get("detail_level"):
                level = user_preferences["detail_level"]
                if language == "fa":
                    pref_additions.append(f"- سطح جزئیات: {level}")
                else:
                    pref_additions.append(f"- Detail level: {level}")
            
            if pref_additions:
                if language == "fa":
                    base_prompt += "\n\nترجیحات کاربر:\n" + "\n".join(pref_additions)
                else:
                    base_prompt += "\n\nUser preferences:\n" + "\n".join(pref_additions)
        
        return base_prompt
    
    def _format_user_preferences(self, preferences: Dict[str, Any], language: str) -> str:
        """Format user preferences into a readable instruction for LLM."""
        if not preferences:
            return ""
        
        instructions = []
        
        if language == "fa":
            if preferences.get("response_style"):
                style_map = {
                    "formal": "رسمی و تخصصی",
                    "casual": "غیررسمی و ساده",
                    "academic": "آکادمیک و علمی",
                    "simple": "ساده و قابل فهم"
                }
                style = style_map.get(preferences["response_style"], preferences["response_style"])
                instructions.append(f"سبک پاسخ: {style}")
            
            if preferences.get("detail_level"):
                level_map = {
                    "brief": "خلاصه و مختصر",
                    "moderate": "متوسط",
                    "comprehensive": "جامع و کامل",
                    "detailed": "با جزئیات کامل"
                }
                level = level_map.get(preferences["detail_level"], preferences["detail_level"])
                instructions.append(f"سطح جزئیات: {level}")
            
            if preferences.get("include_examples"):
                if preferences["include_examples"]:
                    instructions.append("لطفاً مثال‌های عملی ارائه دهید")
            
            if preferences.get("language_style"):
                style_map = {
                    "simple": "از زبان ساده استفاده کنید",
                    "technical": "از اصطلاحات تخصصی استفاده کنید",
                    "mixed": "ترکیبی از زبان ساده و تخصصی"
                }
                style = style_map.get(preferences["language_style"], preferences["language_style"])
                instructions.append(style)
            
            if preferences.get("format"):
                format_map = {
                    "bullet_points": "پاسخ را به صورت نکات کلیدی ارائه دهید",
                    "numbered_list": "پاسخ را به صورت لیست شماره‌دار ارائه دهید",
                    "paragraph": "پاسخ را به صورت پاراگراف‌های منسجم ارائه دهید"
                }
                fmt = format_map.get(preferences["format"], preferences["format"])
                instructions.append(fmt)
            
            if instructions:
                return "راهنمای پاسخ:\n" + "\n".join(f"- {inst}" for inst in instructions)
        
        else:  # English
            if preferences.get("response_style"):
                instructions.append(f"Response style: {preferences['response_style']}")
            
            if preferences.get("detail_level"):
                instructions.append(f"Detail level: {preferences['detail_level']}")
            
            if preferences.get("include_examples") and preferences["include_examples"]:
                instructions.append("Please include practical examples")
            
            if preferences.get("language_style"):
                instructions.append(f"Language style: {preferences['language_style']}")
            
            if preferences.get("format"):
                instructions.append(f"Format: {preferences['format']}")
            
            if instructions:
                return "Response guidelines:\n" + "\n".join(f"- {inst}" for inst in instructions)
        
        return ""
    
    def _extract_sources(self, chunks: List[RAGChunk]) -> List[str]:
        """Extract detailed sources from chunks with full context."""
        sources = []
        seen = set()
        
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.metadata
            source_lines = []
            
            # 1. شماره منبع و متن کامل
            source_lines.append(f"📌 منبع {i}:")
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
                source_lines.append(f"� نام سند: {work_title}")
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
            
            # جلوگیری از تکرار بر اساس document_id + unit_number
            source_key = f"{metadata.get('document_id', '')}_{metadata.get('unit_number', '')}"
            if source_key not in seen:
                sources.append(source)
                seen.add(source_key)
        
        return sources
    
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
