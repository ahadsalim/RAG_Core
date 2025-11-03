"""
OpenAI-Compatible LLM Provider
Implementation for any OpenAI-compatible API (OpenAI, Groq, Together.ai, etc.)
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
import asyncio

import openai
from openai import AsyncOpenAI
import tiktoken
import structlog

from app.llm.base import BaseLLM, LLMConfig, Message, LLMResponse
from app.config.settings import settings

logger = structlog.get_logger()


class OpenAIProvider(BaseLLM):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize OpenAI-compatible provider."""
        if config is None:
            config = LLMConfig(
                provider="openai_compatible",
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        
        super().__init__(config)
        
        # Initialize OpenAI client with custom base_url support
        client_kwargs = {"api_key": config.api_key or settings.llm_api_key}
        if config.base_url or settings.llm_base_url:
            client_kwargs["base_url"] = config.base_url or settings.llm_base_url
            logger.info(f"Using custom base URL: {client_kwargs['base_url']}")
        
        self.client = AsyncOpenAI(**client_kwargs)
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(config.model)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Generate a response from OpenAI."""
        try:
            # Prepare messages
            formatted_messages = self.prepare_messages(messages)
            
            # Merge kwargs with config
            params = {
                "model": self.config.model,
                "messages": formatted_messages,
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "top_p": kwargs.get("top_p", self.config.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.config.frequency_penalty),
                "presence_penalty": kwargs.get("presence_penalty", self.config.presence_penalty),
            }
            
            if self.config.stop_sequences:
                params["stop"] = self.config.stop_sequences
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(**params)
            
            # Extract response
            choice = response.choices[0]
            
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=choice.finish_reason,
                metadata={
                    "id": response.id,
                    "created": response.created,
                }
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise
    
    async def generate_stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from OpenAI."""
        try:
            # Prepare messages
            formatted_messages = self.prepare_messages(messages)
            
            # Merge kwargs with config
            params = {
                "model": self.config.model,
                "messages": formatted_messages,
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "top_p": kwargs.get("top_p", self.config.top_p),
                "stream": True,
            }
            
            # Call OpenAI API with streaming
            stream = await self.client.chat.completions.create(**params)
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
            raise
    
    async def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI."""
        try:
            # Use specified model or default embedding model
            embedding_model = model or settings.openai_embedding_model
            
            # Batch texts if needed (OpenAI has a limit)
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = await self.client.embeddings.create(
                    model=embedding_model,
                    input=batch,
                    **kwargs
                )
                
                # Extract embeddings
                for item in response.data:
                    all_embeddings.append(item.embedding)
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            # Fallback to approximation
            return len(text) // 4


class OpenAIEmbedding:
    """OpenAI embedding service for RAG."""
    
    def __init__(self, model: str = None):
        """Initialize embedding service."""
        self.model = model or settings.openai_embedding_model
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Get embedding dimension
        self.dimension = self._get_model_dimension(self.model)
    
    def _get_model_dimension(self, model: str) -> int:
        """Get embedding dimension for model."""
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dimensions.get(model, 1536)
    
    async def embed_text(self, text: str) -> List[float]:
        """Embed a single text."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """Embed multiple texts in batches."""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                for item in response.data:
                    embeddings.append(item.embedding)
                    
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                raise
        
        return embeddings
