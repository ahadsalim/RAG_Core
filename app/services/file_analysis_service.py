"""
File Analysis Service with LLM
تحلیل فایل‌های ضمیمه شده با استفاده از LLM
"""

from typing import Optional, Dict, Any, List
import base64
import structlog

from app.llm.base import LLMConfig, LLMProvider, Message
from app.llm.openai_provider import OpenAIProvider
from app.config.settings import settings

logger = structlog.get_logger()


class FileAnalysisService:
    """سرویس تحلیل فایل با LLM"""
    
    def __init__(self):
        """Initialize file analysis service with LLM"""
        self.llm_config = LLMConfig(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.2,
            max_tokens=2000,
        )
        self.llm = OpenAIProvider(self.llm_config)
        logger.info("FileAnalysisService initialized")
    
    async def analyze_file(
        self,
        file_url: str,
        filename: str,
        file_type: str,
        user_query: str,
        language: str = "fa"
    ) -> str:
        """
        تحلیل یک فایل منفرد با LLM
        
        Args:
            file_url: آدرس فایل در MinIO
            filename: نام فایل
            file_type: نوع فایل (MIME type)
            user_query: سوال کاربر
            language: زبان
            
        Returns:
            تحلیل فایل
        """
        try:
            from app.services.storage_service import get_storage_service
            from app.services.file_processing_service import get_file_processing_service
            
            # Download file
            storage_service = get_storage_service()
            file_data = await storage_service.download_temp_file(file_url)
            
            # Extract text
            file_processor = get_file_processing_service()
            processing_result = await file_processor.process_file(
                file_data, filename, file_type
            )
            
            # Prepare content
            file_content = [{
                'filename': filename,
                'file_type': file_type,
                'content': processing_result.get('text', ''),
                'is_image': file_type.startswith('image/')
            }]
            
            # Analyze with LLM
            return await self.analyze_files(file_content, user_query, language)
            
        except Exception as e:
            logger.error(f"Failed to analyze file {filename}: {e}")
            return f"خطا در تحلیل فایل {filename}"
    
    async def analyze_files(
        self,
        files_content: List[Dict[str, Any]],
        user_query: str,
        language: str = "fa"
    ) -> str:
        """
        تحلیل فایل‌های ضمیمه شده با LLM
        
        Args:
            files_content: لیست فایل‌ها شامل:
                - filename: نام فایل
                - content: محتوای استخراج شده (متن)
                - file_type: نوع فایل
                - is_image: آیا تصویر است؟
            user_query: سوال کاربر
            language: زبان
            
        Returns:
            تحلیل کامل فایل‌ها
        """
        try:
            # تهیه prompt برای تحلیل
            analysis_prompt = self._build_analysis_prompt(
                files_content,
                user_query,
                language
            )
            
            # ارسال به LLM برای تحلیل
            messages = [
                Message(
                    role="system",
                    content=self._get_system_prompt(language)
                ),
                Message(
                    role="user",
                    content=analysis_prompt
                )
            ]
            
            # استفاده از Responses API برای تحلیل فایل
            response = await self.llm.generate_responses_api(
                messages, 
                reasoning_effort="medium"
            )
            analysis = response.content  # Extract content from LLMResponse
            
            logger.info(
                "Files analyzed (Responses API)",
                file_count=len(files_content),
                analysis_length=len(analysis)
            )
            
            return analysis.strip()
            
        except Exception as e:
            logger.error(f"Failed to analyze files: {e}")
            # در صورت خطا، فقط محتوای خام را برگردان
            return self._fallback_analysis(files_content)
    
    async def analyze_image_with_vision(
        self,
        image_data: bytes,
        filename: str,
        user_query: str,
        language: str = "fa"
    ) -> str:
        """
        تحلیل تصویر با Vision API
        
        Args:
            image_data: داده باینری تصویر
            filename: نام فایل
            user_query: سوال کاربر
            language: زبان
            
        Returns:
            تحلیل تصویر
        """
        try:
            # تبدیل به base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # تهیه prompt
            vision_prompt = f"""تصویر ضمیمه شده را تحلیل کن.
سوال کاربر: {user_query}

لطفاً موارد زیر را ارائه کن:
1. توضیح کامل محتوای تصویر
2. متن موجود در تصویر (اگر وجود دارد)
3. ارتباط تصویر با سوال کاربر
4. نکات مهم و کلیدی

پاسخ را به زبان {'فارسی' if language == 'fa' else 'انگلیسی'} بده."""

            # ارسال به LLM با Vision
            messages = [
                Message(
                    role="user",
                    content=[
                        {
                            "type": "text",
                            "text": vision_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                )
            ]
            
            # استفاده از Responses API برای تحلیل تصویر
            response = await self.llm.generate_responses_api(
                messages,
                reasoning_effort="medium"
            )
            analysis = response.content  # Extract content from LLMResponse
            
            logger.info(
                "Image analyzed with vision (Responses API)",
                filename=filename,
                analysis_length=len(analysis)
            )
            
            return analysis.strip()
            
        except Exception as e:
            logger.error(f"Failed to analyze image with vision: {e}")
            return f"خطا در تحلیل تصویر {filename}"
    
    def _get_system_prompt(self, language: str) -> str:
        """دریافت system prompt برای تحلیل فایل"""
        if language == "fa":
            return """تو یک دستیار هوشمند تحلیل اسناد هستی.
وظیفه‌ات تحلیل فایل‌های ضمیمه شده و استخراج اطلاعات مهم است.

برای هر فایل:
1. خلاصه محتوا را ارائه کن
2. نکات کلیدی و مهم را استخراج کن
3. ارتباط محتوا با سوال کاربر را مشخص کن
4. اگر جدول یا داده عددی وجود دارد، آن را تفسیر کن

پاسخ را مختصر، دقیق و کاربردی بنویس."""
        else:
            return """You are an intelligent document analysis assistant.
Your task is to analyze attached files and extract important information.

For each file:
1. Provide a summary of the content
2. Extract key points
3. Identify relevance to user's question
4. Interpret tables or numerical data if present

Keep the response concise, accurate and practical."""
    
    def _build_analysis_prompt(
        self,
        files_content: List[Dict[str, Any]],
        user_query: str,
        language: str
    ) -> str:
        """ساخت prompt برای تحلیل فایل‌ها"""
        parts = []
        
        if language == "fa":
            parts.append(f"سوال کاربر: {user_query}\n")
            parts.append(f"تعداد فایل‌های ضمیمه: {len(files_content)}\n")
            
            for i, file_info in enumerate(files_content, 1):
                parts.append(f"\n--- فایل {i}: {file_info['filename']} ---")
                parts.append(f"نوع: {file_info['file_type']}")
                
                if file_info.get('is_image'):
                    parts.append("(این فایل یک تصویر است)")
                
                content = file_info.get('content', '')
                if content:
                    # محدود کردن طول محتوا
                    max_length = 3000
                    if len(content) > max_length:
                        content = content[:max_length] + "\n... (ادامه دارد)"
                    parts.append(f"\nمحتوا:\n{content}")
                else:
                    parts.append("\n(محتوای متنی استخراج نشد)")
            
            parts.append("\n\nلطفاً این فایل‌ها را تحلیل کن و اطلاعات مهم را استخراج کن.")
        else:
            parts.append(f"User's question: {user_query}\n")
            parts.append(f"Number of attached files: {len(files_content)}\n")
            
            for i, file_info in enumerate(files_content, 1):
                parts.append(f"\n--- File {i}: {file_info['filename']} ---")
                parts.append(f"Type: {file_info['file_type']}")
                
                if file_info.get('is_image'):
                    parts.append("(This is an image file)")
                
                content = file_info.get('content', '')
                if content:
                    max_length = 3000
                    if len(content) > max_length:
                        content = content[:max_length] + "\n... (continued)"
                    parts.append(f"\nContent:\n{content}")
                else:
                    parts.append("\n(No text content extracted)")
            
            parts.append("\n\nPlease analyze these files and extract important information.")
        
        return "\n".join(parts)
    
    def _fallback_analysis(self, files_content: List[Dict[str, Any]]) -> str:
        """تحلیل ساده در صورت خطا در LLM"""
        parts = ["محتوای فایل‌های ضمیمه:\n"]
        
        for i, file_info in enumerate(files_content, 1):
            parts.append(f"\n{i}. {file_info['filename']} ({file_info['file_type']})")
            content = file_info.get('content', '')
            if content:
                # محدود کردن طول
                if len(content) > 500:
                    content = content[:500] + "..."
                parts.append(content)
        
        return "\n".join(parts)


# Singleton instance
_file_analysis_service = None


def get_file_analysis_service() -> FileAnalysisService:
    """Get file analysis service instance"""
    global _file_analysis_service
    if _file_analysis_service is None:
        _file_analysis_service = FileAnalysisService()
    return _file_analysis_service
