"""
User Memory Management API Endpoints
=====================================
API برای مدیریت حافظه بلندمدت کاربر

این endpoint ها توسط سیستم کاربران فراخوانی می‌شوند.
"""

from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import structlog

from app.db.session import get_db
from app.models.user import UserProfile, UserMemory, MemoryCategory
from app.core.security import get_current_user_id
from app.services.long_term_memory import get_long_term_memory_service

logger = structlog.get_logger()
router = APIRouter()


# ==================== Request/Response Models ====================

class MemoryItemResponse(BaseModel):
    """یک آیتم حافظه"""
    id: str
    content: str
    category: str
    confidence: float
    usage_count: int
    created_at: Optional[str]
    updated_at: Optional[str]


class MemoryListResponse(BaseModel):
    """لیست حافظه‌های کاربر"""
    user_id: str
    memories: List[MemoryItemResponse]
    total_count: int


class UpdateMemoryRequest(BaseModel):
    """درخواست ویرایش حافظه"""
    content: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, description="personal_info|preference|goal|interest|context|behavior|other")


class AddMemoryRequest(BaseModel):
    """درخواست افزودن حافظه دستی"""
    content: str = Field(..., min_length=1, max_length=500)
    category: str = Field(default="other", description="personal_info|preference|goal|interest|context|behavior|other")


class SummarizeResponse(BaseModel):
    """پاسخ خلاصه‌سازی"""
    success: bool
    before_count: int
    after_count: int
    message: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/", response_model=MemoryListResponse)
async def get_user_memories(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    دریافت لیست تمام حافظه‌های بلندمدت کاربر
    
    این endpoint توسط سیستم کاربران برای نمایش حافظه‌ها به کاربر استفاده می‌شود.
    """
    try:
        memory_service = get_long_term_memory_service()
        memories = await memory_service.get_user_memories(db, user_id)
        
        return MemoryListResponse(
            user_id=user_id,
            memories=[
                MemoryItemResponse(
                    id=m["id"],
                    content=m["content"],
                    category=m["category"],
                    confidence=m["confidence"],
                    usage_count=m["usage_count"],
                    created_at=m["created_at"],
                    updated_at=m["updated_at"]
                )
                for m in memories
            ],
            total_count=len(memories)
        )
        
    except Exception as e:
        logger.error(f"Failed to get user memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memories"
        )


@router.get("/{memory_id}", response_model=MemoryItemResponse)
async def get_memory_item(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """دریافت یک آیتم حافظه خاص"""
    try:
        memory_service = get_long_term_memory_service()
        memories = await memory_service.get_user_memories(db, user_id)
        
        for m in memories:
            if m["id"] == memory_id:
                return MemoryItemResponse(
                    id=m["id"],
                    content=m["content"],
                    category=m["category"],
                    confidence=m["confidence"],
                    usage_count=m["usage_count"],
                    created_at=m["created_at"],
                    updated_at=m["updated_at"]
                )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory"
        )


@router.post("/", response_model=MemoryItemResponse)
async def add_memory(
    request: AddMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    افزودن حافظه جدید به صورت دستی
    
    کاربر می‌تواند اطلاعاتی را که می‌خواهد سیستم به یاد داشته باشد، اضافه کند.
    """
    try:
        memory_service = get_long_term_memory_service()
        
        # ادغام با حافظه‌های موجود
        result = await memory_service.merge_memory(
            db=db,
            user_id=user_id,
            new_memory=request.content,
            category=request.category
        )
        
        if result["action"] == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add memory"
            )
        
        # دریافت حافظه اضافه شده
        memories = await memory_service.get_user_memories(db, user_id)
        
        if result["memory_id"]:
            for m in memories:
                if m["id"] == result["memory_id"]:
                    return MemoryItemResponse(
                        id=m["id"],
                        content=m["content"],
                        category=m["category"],
                        confidence=m["confidence"],
                        usage_count=m["usage_count"],
                        created_at=m["created_at"],
                        updated_at=m["updated_at"]
                    )
        
        # اگر skip شد
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory already exists or was merged with existing memory"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add memory"
        )


@router.put("/{memory_id}", response_model=MemoryItemResponse)
async def update_memory(
    memory_id: str,
    request: UpdateMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    ویرایش یک آیتم حافظه
    
    کاربر می‌تواند محتوا یا دسته‌بندی حافظه را تغییر دهد.
    """
    try:
        memory_service = get_long_term_memory_service()
        
        success = await memory_service.update_memory_content(
            db=db,
            user_id=user_id,
            memory_id=memory_id,
            new_content=request.content,
            new_category=request.category
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found or update failed"
            )
        
        # دریافت حافظه به‌روز شده
        memories = await memory_service.get_user_memories(db, user_id)
        
        for m in memories:
            if m["id"] == memory_id:
                return MemoryItemResponse(
                    id=m["id"],
                    content=m["content"],
                    category=m["category"],
                    confidence=m["confidence"],
                    usage_count=m["usage_count"],
                    created_at=m["created_at"],
                    updated_at=m["updated_at"]
                )
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found after update"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update memory"
        )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    حذف یک آیتم حافظه
    
    کاربر می‌تواند هر حافظه‌ای را که نمی‌خواهد حذف کند.
    """
    try:
        memory_service = get_long_term_memory_service()
        
        success = await memory_service.delete_memory(
            db=db,
            user_id=user_id,
            memory_id=memory_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        return {"success": True, "message": "Memory deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory"
        )


@router.delete("/")
async def clear_all_memories(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    پاک کردن تمام حافظه‌های کاربر
    
    ⚠️ این عمل غیرقابل بازگشت است!
    """
    try:
        memory_service = get_long_term_memory_service()
        
        count = await memory_service.clear_all_memories(db, user_id)
        
        return {
            "success": True,
            "message": f"All {count} memories cleared",
            "deleted_count": count
        }
        
    except Exception as e:
        logger.error(f"Failed to clear memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear memories"
        )


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_memories(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    خلاصه‌سازی و تمیزکاری حافظه‌ها
    
    این endpoint حافظه‌های تکراری را ادغام و موارد قدیمی را حذف می‌کند.
    """
    try:
        memory_service = get_long_term_memory_service()
        
        result = await memory_service.summarize_memories(db, user_id)
        
        return SummarizeResponse(
            success=result.get("success", False),
            before_count=result.get("before_count", 0),
            after_count=result.get("after_count", 0),
            message=result.get("message") or result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Failed to summarize memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to summarize memories"
        )


@router.get("/context/text")
async def get_memory_context_text(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    دریافت context حافظه به صورت متن
    
    این endpoint برای دیباگ و نمایش به کاربر استفاده می‌شود.
    """
    try:
        memory_service = get_long_term_memory_service()
        
        context = await memory_service.get_memory_context(db, user_id)
        
        return {
            "user_id": user_id,
            "context": context or "هیچ حافظه‌ای ذخیره نشده است.",
            "has_memories": context is not None
        }
        
    except Exception as e:
        logger.error(f"Failed to get memory context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get memory context"
        )
