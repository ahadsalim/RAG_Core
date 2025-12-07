"""
LLM Factory with Fallback Support

این ماژول یک factory برای ایجاد LLM با پشتیبانی از fallback ارائه می‌دهد.
اگر primary provider در دسترس نباشد، به صورت خودکار از fallback استفاده می‌شود.
"""

import asyncio
from typing import Optional, List
import structlog

from app.llm.base import LLMConfig, LLMProvider, Message, LLMResponse
from app.llm.openai_provider import OpenAIProvider
from app.llm.state import is_primary_llm_down, set_primary_llm_down
from app.config.settings import settings

logger = structlog.get_logger()


class LLMWithFallback:
    """
    LLM wrapper با پشتیبانی از fallback
    
    اگر primary LLM با خطا مواجه شود، به صورت خودکار از fallback استفاده می‌کند.
    """
    
    def __init__(
        self,
        primary_config: Optional[LLMConfig] = None,
        fallback_config: Optional[LLMConfig] = None,
        timeout: float = 30.0
    ):
        """
        Initialize LLM with fallback support
        
        Args:
            primary_config: تنظیمات LLM اصلی
            fallback_config: تنظیمات LLM پشتیبان
            timeout: زمان انتظار برای هر provider (ثانیه)
        """
        self.timeout = timeout
        
        # Primary LLM
        if primary_config:
            self.primary_config = primary_config
        else:
            self.primary_config = LLMConfig(
                provider=LLMProvider.OPENAI_COMPATIBLE,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        self.primary_llm = OpenAIProvider(self.primary_config)
        
        # Fallback LLM
        self.fallback_llm = None
        self.fallback_config = None
        
        if fallback_config:
            self.fallback_config = fallback_config
            self.fallback_llm = OpenAIProvider(self.fallback_config)
        elif settings.llm_fallback_api_key:
            self.fallback_config = LLMConfig(
                provider=LLMProvider.OPENAI_COMPATIBLE,
                model=settings.llm_fallback_model or "gpt-4o-mini",
                api_key=settings.llm_fallback_api_key,
                base_url=settings.llm_fallback_base_url or "https://api.openai.com/v1",
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
            self.fallback_llm = OpenAIProvider(self.fallback_config)
        
        # برای سازگاری با کدهای قدیمی که از self.llm.config استفاده می‌کنند
        self.config = self.primary_config
        
        logger.info(
            f"LLMWithFallback initialized",
            primary_model=self.primary_config.model,
            primary_url=self.primary_config.base_url,
            has_fallback=self.fallback_llm is not None,
            fallback_model=self.fallback_config.model if self.fallback_config else None,
        )
    
    async def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate response with automatic fallback
        اگر primary قبلاً down شده (مثلاً در classification)، مستقیم از fallback استفاده می‌کند
        
        Args:
            messages: لیست پیام‌ها
            
        Returns:
            LLMResponse از primary یا fallback
        """
        timeout = settings.llm_primary_timeout  # یک تایم‌اوت برای همه
        
        # اگر primary قبلاً down شده، مستقیم به fallback برو
        if is_primary_llm_down():
            logger.info("Primary LLM is marked as DOWN, using fallback directly for generation")
            if self.fallback_llm:
                return await self._call_fallback(messages, timeout)
            else:
                raise Exception("Primary LLM is down and no fallback configured")
        
        # تلاش با Primary
        try:
            logger.debug(f"Trying primary LLM: {self.primary_config.model}")
            response = await asyncio.wait_for(
                self.primary_llm.generate(messages),
                timeout=timeout
            )
            logger.info("Primary LLM responded successfully")
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Primary LLM timeout ({timeout}s)")
            set_primary_llm_down(True)
        except Exception as e:
            logger.warning(f"Primary LLM failed: {e}")
            set_primary_llm_down(True)
        
        # تلاش با Fallback
        if self.fallback_llm:
            return await self._call_fallback(messages, timeout)
        else:
            raise Exception("Primary LLM failed and no fallback configured")
    
    async def _call_fallback(self, messages: List[Message], timeout: float) -> LLMResponse:
        """فراخوانی Fallback LLM"""
        try:
            logger.info(f"Trying fallback LLM: {self.fallback_config.model}")
            response = await asyncio.wait_for(
                self.fallback_llm.generate(messages),
                timeout=timeout
            )
            logger.info("Fallback LLM responded successfully")
            return response
        except asyncio.TimeoutError:
            logger.error(f"Fallback LLM timeout ({timeout}s)")
            raise Exception("Fallback LLM timed out")
        except Exception as e:
            logger.error(f"Fallback LLM failed: {e}")
            raise Exception(f"Fallback LLM failed: {e}")
    
    async def generate_stream(self, messages: List[Message]):
        """
        Generate streaming response with automatic fallback
        اگر primary قبلاً down شده، مستقیم از fallback استفاده می‌کند
        
        Args:
            messages: لیست پیام‌ها
            
        Yields:
            chunks از primary یا fallback
        """
        # اگر primary قبلاً down شده، مستقیم به fallback برو
        if is_primary_llm_down():
            logger.info("Primary LLM is marked as DOWN, using fallback directly for streaming")
            if self.fallback_llm:
                async for chunk in self.fallback_llm.generate_stream(messages):
                    yield chunk
                logger.info("Fallback LLM stream completed")
                return
            else:
                raise Exception("Primary LLM is down and no fallback configured")
        
        # تلاش با Primary
        try:
            logger.debug(f"Trying primary LLM stream: {self.primary_config.model}")
            async for chunk in self.primary_llm.generate_stream(messages):
                yield chunk
            logger.info("Primary LLM stream completed")
            return
        except asyncio.TimeoutError:
            logger.warning(f"Primary LLM stream timeout")
            set_primary_llm_down(True)
        except Exception as e:
            logger.warning(f"Primary LLM stream failed: {e}")
            set_primary_llm_down(True)
        
        # تلاش با Fallback
        if self.fallback_llm:
            try:
                logger.info(f"Trying fallback LLM stream: {self.fallback_config.model}")
                async for chunk in self.fallback_llm.generate_stream(messages):
                    yield chunk
                logger.info("Fallback LLM stream completed")
                return
            except Exception as e:
                logger.error(f"Fallback LLM stream failed: {e}")
                raise Exception(f"Fallback LLM stream failed: {e}")
        else:
            raise Exception("Primary LLM stream failed and no fallback configured")


def create_llm1_light() -> LLMWithFallback:
    """
    ایجاد LLM1 (Light) برای سوالات ساده
    استفاده برای: invalid_no_file, invalid_with_file, general_no_business
    """
    primary_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model=settings.llm1_model,
        api_key=settings.llm1_api_key,
        base_url=settings.llm1_base_url,
        max_tokens=settings.llm1_max_tokens,
        temperature=settings.llm1_temperature,
    )
    
    fallback_config = None
    if settings.llm1_fallback_api_key:
        fallback_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm1_fallback_model or settings.llm1_model,
            api_key=settings.llm1_fallback_api_key,
            base_url=settings.llm1_fallback_base_url or "https://api.openai.com/v1",
            max_tokens=settings.llm1_max_tokens,
            temperature=settings.llm1_temperature,
        )
    
    logger.info(f"Creating LLM1 (Light): {settings.llm1_model}")
    return LLMWithFallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
        timeout=settings.llm_primary_timeout
    )


def create_llm2_pro() -> LLMWithFallback:
    """
    ایجاد LLM2 (Pro) برای سوالات کسب‌وکار
    استفاده برای: business_no_file, business_with_file
    """
    primary_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model=settings.llm2_model,
        api_key=settings.llm2_api_key,
        base_url=settings.llm2_base_url,
        max_tokens=settings.llm2_max_tokens,
        temperature=settings.llm2_temperature,
    )
    
    fallback_config = None
    if settings.llm2_fallback_api_key:
        fallback_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm2_fallback_model or settings.llm2_model,
            api_key=settings.llm2_fallback_api_key,
            base_url=settings.llm2_fallback_base_url or "https://api.openai.com/v1",
            max_tokens=settings.llm2_max_tokens,
            temperature=settings.llm2_temperature,
        )
    
    logger.info(f"Creating LLM2 (Pro): {settings.llm2_model}")
    return LLMWithFallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
        timeout=settings.llm_primary_timeout
    )


def get_llm_for_category(category: str) -> LLMWithFallback:
    """
    انتخاب LLM مناسب بر اساس دسته‌بندی سوال
    
    Args:
        category: دسته‌بندی سوال از classifier
        
    Returns:
        LLMWithFallback مناسب
    """
    # LLM1 (Light) برای سوالات ساده
    if category in ["invalid_no_file", "invalid_with_file", "general_no_business"]:
        return create_llm1_light()
    
    # LLM2 (Pro) برای سوالات کسب‌وکار
    elif category in ["business_no_file", "business_with_file"]:
        return create_llm2_pro()
    
    # پیش‌فرض: LLM2 (Pro)
    else:
        logger.warning(f"Unknown category '{category}', defaulting to LLM2 (Pro)")
        return create_llm2_pro()
