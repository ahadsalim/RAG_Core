"""
OpenAI-Compatible LLM Provider
Implementation for any OpenAI-compatible API (OpenAI, Groq, Together.ai, etc.)
Uses Responses API for GPT-5 models
"""

from typing import List, Dict, Any, Optional
import asyncio

import openai
from openai import AsyncOpenAI, OpenAI
import tiktoken
import structlog

from app.llm.base import BaseLLM, LLMConfig, Message, LLMResponse
from app.config.settings import settings

logger = structlog.get_logger()


def extract_responses_api_text(response) -> str:
    """Extract text from Responses API response"""
    # Method 1: output_text (direct attribute) - PREFERRED
    if hasattr(response, 'output_text') and response.output_text:
        return response.output_text
    
    # Method 2: output -> content -> text
    if hasattr(response, 'output') and response.output:
        for output_item in response.output:
            if hasattr(output_item, 'content') and output_item.content:
                for content_item in output_item.content:
                    if hasattr(content_item, 'text') and content_item.text:
                        return content_item.text
    
    # Method 3: Check if output is a list of message objects
    if hasattr(response, 'output') and response.output:
        for item in response.output:
            if hasattr(item, 'text') and item.text:
                return item.text
            if hasattr(item, 'type') and item.type == 'message':
                if hasattr(item, 'content') and item.content:
                    for c in item.content:
                        if hasattr(c, 'text'):
                            return c.text
    
    return ""


def extract_responses_api_tokens(response) -> tuple:
    """Extract token counts from Responses API response"""
    input_tokens = 0
    output_tokens = 0
    
    if hasattr(response, 'usage') and response.usage:
        input_tokens = getattr(response.usage, 'input_tokens', 0) or 0
        output_tokens = getattr(response.usage, 'output_tokens', 0) or 0
    
    return input_tokens, output_tokens


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
        # Sync client for Responses API (which doesn't have async version yet)
        self.sync_client = OpenAI(**client_kwargs)
        
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
            max_tokens_value = kwargs.get("max_tokens", self.config.max_tokens)
            
            # مدل‌های جدید (gpt-5, o1, o3) محدودیت‌های خاصی دارند
            is_new_model = any(x in self.config.model for x in ["gpt-5", "o1", "o3"])
            
            params = {
                "model": self.config.model,
                "messages": formatted_messages,
            }
            
            # مدل‌های جدید از temperature و top_p پشتیبانی نمی‌کنند
            if not is_new_model:
                params["temperature"] = kwargs.get("temperature", self.config.temperature)
                params["top_p"] = kwargs.get("top_p", self.config.top_p)
                params["frequency_penalty"] = kwargs.get("frequency_penalty", self.config.frequency_penalty)
                params["presence_penalty"] = kwargs.get("presence_penalty", self.config.presence_penalty)
            
            # gpt-5-nano و مدل‌های جدید از max_completion_tokens استفاده می‌کنند
            if is_new_model:
                params["max_completion_tokens"] = max_tokens_value
            else:
                params["max_tokens"] = max_tokens_value
            
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
    
    async def generate_responses_api(
        self,
        messages: List[Message],
        reasoning_effort: str = "low",
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response using OpenAI Responses API.
        This is the newer API that supports reasoning models.
        
        Args:
            messages: List of messages (will be converted to input format)
            reasoning_effort: "low", "medium", or "high"
            **kwargs: Additional parameters (input_content for direct input)
        
        Returns:
            LLMResponse with content and usage info
        """
        try:
            max_tokens_value = kwargs.get("max_tokens", self.config.max_tokens)
            
            # اگر input_content مستقیم داده شده، از آن استفاده کن (مانند فایل تست)
            if "input_content" in kwargs:
                input_content = kwargs["input_content"]
            else:
                # Convert messages to input format for Responses API
                formatted_messages = self.prepare_messages(messages)
                
                # Build input content
                input_parts = []
                for msg in formatted_messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "system":
                        input_parts.append(content)
                    elif role == "user":
                        input_parts.append(f"\n---\n\n{content}")
                    elif role == "assistant":
                        input_parts.append(f"\n[Assistant]: {content}")
                
                input_content = "\n".join(input_parts)
            
            # Run sync client in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sync_client.responses.create(
                    model=self.config.model,
                    input=input_content,
                    reasoning={"effort": reasoning_effort},
                    max_output_tokens=max_tokens_value,
                )
            )
            
            # Extract response text
            content = extract_responses_api_text(response)
            input_tokens, output_tokens = extract_responses_api_tokens(response)
            
            return LLMResponse(
                content=content,
                model=self.config.model,
                usage={
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                finish_reason="stop",
                metadata={
                    "api_type": "responses",
                    "reasoning_effort": reasoning_effort,
                }
            )
            
        except Exception as e:
            logger.error(f"OpenAI Responses API failed: {e}")
            raise


# NOTE: OpenAIEmbedding class has been removed.
# Use app.services.embedding_service.EmbeddingService instead for all embedding needs.
# The unified EmbeddingService supports both API-based and local embeddings automatically.
