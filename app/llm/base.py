"""
Base LLM Interface
Abstract base class for LLM providers
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
import enum


class LLMProvider(enum.Enum):
    """Supported LLM providers."""
    OPENAI_COMPATIBLE = "openai_compatible"  # For all OpenAI-compatible APIs


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    

@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None
    

@dataclass
class LLMResponse:
    """LLM response."""
    content: str
    model: str
    usage: Dict[str, int]  # tokens used
    finish_reason: str
    metadata: Optional[Dict[str, Any]] = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: LLMConfig):
        """Initialize LLM with configuration."""
        self.config = config
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of chat messages
            **kwargs: Additional parameters
            
        Returns:
            LLM response
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.
        
        Args:
            messages: List of chat messages
            **kwargs: Additional parameters
            
        Yields:
            Response chunks
        """
        pass
    
    @abstractmethod
    async def embed(
        self,
        texts: List[str],
        **kwargs
    ) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    async def count_tokens(
        self,
        text: str
    ) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
    
    def prepare_messages(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Prepare messages for API call.
        
        Args:
            messages: List of chat messages
            system_prompt: Optional system prompt to prepend
            
        Returns:
            Formatted messages
        """
        formatted = []
        
        if system_prompt:
            formatted.append({
                "role": "system",
                "content": system_prompt
            })
        
        for msg in messages:
            formatted.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return formatted
