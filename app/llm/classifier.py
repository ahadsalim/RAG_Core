"""
LLM-based Query Classifier

این ماژول مسئول دسته‌بندی سوالات کاربر است:
- احوالپرسی، چرت‌وپرت، فحش → پاسخ مستقیم
- سوال واقعی → ادامه به RAG Pipeline
"""

import json
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.llm.base import LLMConfig, LLMProvider, Message
from app.llm.openai_provider import OpenAIProvider
from app.llm.state import is_primary_llm_down, set_primary_llm_down
from app.config.settings import settings
from app.config.prompts import ClassificationPrompts
import structlog

logger = structlog.get_logger()


class QueryCategory(BaseModel):
    """دسته‌بندی سوال"""
    category: str  # "invalid_no_file", "invalid_with_file", "general", "business_no_file", "business_with_file"
    confidence: float  # 0.0 to 1.0
    direct_response: Optional[str] = None  # پاسخ مستقیم برای موارد غیر سوالی
    has_meaningful_files: Optional[bool] = None  # آیا فایل‌ها معنادار هستند؟
    needs_clarification: bool = False  # آیا نیاز به توضیح بیشتر دارد؟
    needs_web_search: bool = False  # آیا نیاز به جستجوی وب دارد؟


class QueryClassifier:
    """دسته‌بندی کننده سوالات با LLM و پشتیبانی از Fallback"""
    
    def __init__(self):
        """Initialize classifier with primary and fallback LLM"""
        from app.config.prompts import LLMConfig as LLMConfigPresets
        
        config_presets = LLMConfigPresets.get_config_for_classification()
        
        # --- Primary LLM ---
        self.primary_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_classification_model or settings.llm_model,
            api_key=settings.llm_classification_api_key or settings.llm_api_key,
            base_url=settings.llm_classification_base_url or settings.llm_base_url,
            temperature=settings.llm_classification_temperature or config_presets["temperature"],
            max_tokens=settings.llm_classification_max_tokens or config_presets["max_tokens"],
        )
        self.primary_llm = OpenAIProvider(self.primary_config)
        
        # --- Fallback LLM ---
        self.fallback_llm = None
        fallback_api_key = settings.llm_classification_fallback_api_key or settings.llm_fallback_api_key
        if fallback_api_key:
            self.fallback_config = LLMConfig(
                provider=LLMProvider.OPENAI_COMPATIBLE,
                model=settings.llm_classification_fallback_model or settings.llm_fallback_model or "gpt-4o-mini",
                api_key=fallback_api_key,
                base_url=settings.llm_classification_fallback_base_url or settings.llm_fallback_base_url or "https://api.openai.com/v1",
                temperature=settings.llm_classification_temperature or config_presets["temperature"],
                max_tokens=settings.llm_classification_max_tokens or config_presets["max_tokens"],
            )
            self.fallback_llm = OpenAIProvider(self.fallback_config)
            logger.info(f"QueryClassifier fallback initialized: {self.fallback_config.model} @ {self.fallback_config.base_url}")
        
        # For backward compatibility
        self.llm_config = self.primary_config
        self.llm = self.primary_llm
        
        logger.info(f"QueryClassifier primary initialized: {self.primary_config.model} @ {self.primary_config.base_url}")
    
    async def classify(
        self,
        query: str,
        language: str = "fa",
        context: Optional[str] = None,
        file_analysis: Optional[str] = None
    ) -> QueryCategory:
        """
        دسته‌بندی سوال کاربر با در نظر گرفتن context و فایل‌ها
        
        Args:
            query: متن سوال کاربر
            language: زبان سوال (fa یا en)
            context: خلاصه مکالمات قبلی
            file_analysis: تحلیل فایل‌های ضمیمه
        
        Returns:
            QueryCategory با دسته، اطمینان، و پاسخ مستقیم (در صورت نیاز)
        """
        try:
            # ساخت prompt برای دسته‌بندی
            system_prompt = self._build_classification_prompt()
            
            # ساخت پیام کاربر با context و file_analysis
            user_message_parts = []
            
            if context:
                user_message_parts.append(f"خلاصه مکالمات قبلی:\n{context}\n")
            
            if file_analysis:
                user_message_parts.append(f"تحلیل فایل‌های ضمیمه:\n{file_analysis}\n")
            
            user_message_parts.append(f"سوال فعلی کاربر: {query}")
            user_message = "\n".join(user_message_parts)
            
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_message)
            ]
            
            # تلاش با Primary LLM
            response = await self._try_llm_with_fallback(messages)
            
            # پارس کردن پاسخ JSON
            result = self._parse_classification_response(response)
            
            logger.info(
                f"Query classified: category={result.category}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Classification failed (all providers): {e}")
            # در صورت خطا، فرض می‌کنیم سوال واقعی است
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                needs_clarification=False
            )
    
    async def _try_llm_with_fallback(self, messages: list) -> str:
        """
        تلاش برای فراخوانی LLM با fallback در صورت خطا
        اگر primary قبلاً down شده، مستقیم از fallback استفاده می‌کند
        
        Args:
            messages: لیست پیام‌ها
            
        Returns:
            محتوای پاسخ LLM
        """
        timeout = settings.llm_primary_timeout
        
        # اگر primary قبلاً down شده، مستقیم به fallback برو
        if is_primary_llm_down():
            logger.info("Primary LLM is marked as DOWN, using fallback directly")
            if self.fallback_llm:
                return await self._call_fallback(messages, timeout)
            else:
                raise Exception("Primary LLM is down and no fallback configured")
        
        # تلاش با Primary - استفاده از Responses API برای مدل‌های جدید
        try:
            logger.debug(f"Trying primary LLM (Responses API): {self.primary_config.model}")
            response = await asyncio.wait_for(
                self.primary_llm.generate_responses_api(messages, reasoning_effort="low"),
                timeout=timeout
            )
            logger.info("Primary LLM (Responses API) responded successfully")
            return response.content
        except asyncio.TimeoutError:
            logger.warning(f"Primary LLM timeout ({timeout}s)")
            set_primary_llm_down(True)  # Mark primary as down
        except Exception as e:
            logger.warning(f"Primary LLM failed: {e}")
            set_primary_llm_down(True)  # Mark primary as down
        
        # تلاش با Fallback
        if self.fallback_llm:
            return await self._call_fallback(messages, timeout)
        else:
            raise Exception("Primary LLM failed and no fallback configured")
    
    async def _call_fallback(self, messages: list, timeout: float) -> str:
        """فراخوانی Fallback LLM با Responses API"""
        try:
            logger.info(f"Trying fallback LLM (Responses API): {self.fallback_config.model}")
            response = await asyncio.wait_for(
                self.fallback_llm.generate_responses_api(messages, reasoning_effort="low"),
                timeout=settings.llm_primary_timeout
            )
            logger.info("Fallback LLM (Responses API) responded successfully")
            return response.content
        except asyncio.TimeoutError:
            logger.error(f"Fallback LLM timeout ({settings.llm_primary_timeout}s)")
            raise Exception("Fallback LLM timed out")
        except Exception as e:
            logger.error(f"Fallback LLM failed: {e}")
            raise Exception(f"Fallback LLM failed: {e}")
    
    def _build_classification_prompt(self) -> str:
        """دریافت prompt دسته‌بندی از فایل prompts.py"""
        return ClassificationPrompts.get_classification_prompt()
    
    def _parse_classification_response(self, response: str) -> QueryCategory:
        """پارس کردن پاسخ JSON از LLM"""
        try:
            # حذف markdown code blocks اگر وجود داشت
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # پارس JSON
            data = json.loads(response)
            
            return QueryCategory(
                category=data.get("category", "business_no_file"),
                confidence=float(data.get("confidence", 0.5)),
                direct_response=data.get("direct_response"),
                has_meaningful_files=data.get("has_meaningful_files"),
                needs_clarification=data.get("needs_clarification", False),
                needs_web_search=data.get("needs_web_search", False)
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            logger.warning(f"Raw response was: '{response[:500] if response else 'EMPTY'}'")
            
            # fallback: تشخیص دستی
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["invalid_no_file", "نامعتبر", "بی‌معنی"]):
                return QueryCategory(
                    category="invalid_no_file",
                    confidence=0.7,
                    direct_response="متن شما قابل فهم نیست. لطفاً سوال خود را به صورت واضح بپرسید.",
                    needs_clarification=True
                )
            
            # پیش‌فرض: سوال کسب و کار
            return QueryCategory(
                category="business_no_file",
                confidence=0.5,
                needs_clarification=False
            )
