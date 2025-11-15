"""
Celery Tasks Management API Endpoints
Endpoints for monitoring and managing async tasks
"""

from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
import structlog

from app.config.settings import settings
from celery.result import AsyncResult
from app.celery_app import celery_app

logger = structlog.get_logger()
router = APIRouter()


# Response Models
class TaskStatusResponse(BaseModel):
    """Task status response model."""
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    traceback: Optional[str] = None


class TaskListResponse(BaseModel):
    """Task list response model."""
    active: list[Dict[str, Any]]
    scheduled: list[Dict[str, Any]]
    reserved: list[Dict[str, Any]]


# API key dependency
async def verify_admin_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify API key for admin operations."""
    if x_api_key not in {settings.ingest_api_key, settings.users_api_key}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key


# Get task status
@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """
    Get status of a specific Celery task.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status and result
    """
    try:
        task = AsyncResult(task_id, app=celery_app)
        
        response = TaskStatusResponse(
            task_id=task_id,
            status=task.status,
            result=task.result if task.successful() else None,
            error=str(task.result) if task.failed() else None,
            traceback=task.traceback if task.failed() else None
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


# List active tasks
@router.get("/list", response_model=TaskListResponse)
async def list_tasks(
    api_key: str = Depends(verify_admin_api_key)
):
    """
    List all active, scheduled, and reserved tasks.
    
    Returns:
        Lists of tasks by status
    """
    try:
        # Get active tasks from all workers
        inspect = celery_app.control.inspect()
        
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
        
        # Flatten worker-specific lists
        active_tasks = []
        for worker, tasks in active.items():
            for task in tasks:
                task['worker'] = worker
                active_tasks.append(task)
        
        scheduled_tasks = []
        for worker, tasks in scheduled.items():
            for task in tasks:
                task['worker'] = worker
                scheduled_tasks.append(task)
        
        reserved_tasks = []
        for worker, tasks in reserved.items():
            for task in tasks:
                task['worker'] = worker
                reserved_tasks.append(task)
        
        return TaskListResponse(
            active=active_tasks,
            scheduled=scheduled_tasks,
            reserved=reserved_tasks
        )
        
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


# Revoke task
@router.post("/revoke/{task_id}")
async def revoke_task(
    task_id: str,
    terminate: bool = False,
    api_key: str = Depends(verify_admin_api_key)
):
    """
    Revoke (cancel) a running task.
    
    Args:
        task_id: Celery task ID
        terminate: If True, terminate the task immediately
        
    Returns:
        Revoke result
    """
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        
        logger.info(
            f"Task revoked: {task_id}",
            terminate=terminate
        )
        
        return {
            "status": "success",
            "task_id": task_id,
            "terminated": terminate
        }
        
    except Exception as e:
        logger.error(f"Failed to revoke task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke task: {str(e)}"
        )


# Get worker statistics
@router.get("/workers")
async def get_worker_stats(
    api_key: str = Depends(verify_admin_api_key)
):
    """
    Get statistics for all Celery workers.
    
    Returns:
        Worker statistics
    """
    try:
        inspect = celery_app.control.inspect()
        
        stats = inspect.stats() or {}
        active_queues = inspect.active_queues() or {}
        registered = inspect.registered() or {}
        
        workers = []
        for worker_name, worker_stats in stats.items():
            workers.append({
                "name": worker_name,
                "stats": worker_stats,
                "queues": active_queues.get(worker_name, []),
                "registered_tasks": registered.get(worker_name, [])
            })
        
        return {
            "status": "success",
            "workers": workers,
            "total_workers": len(workers)
        }
        
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get worker stats: {str(e)}"
        )


# Trigger manual tasks
@router.post("/trigger/cleanup-cache")
async def trigger_cleanup_cache(
    api_key: str = Depends(verify_admin_api_key)
):
    """Manually trigger cache cleanup task."""
    try:
        from app.tasks.cleanup import cleanup_old_cache
        task = cleanup_old_cache.delay()
        
        return {
            "status": "initiated",
            "task_id": task.id,
            "message": "Cache cleanup task started"
        }
    except Exception as e:
        logger.error(f"Failed to trigger cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/reset-daily-limits")
async def trigger_reset_daily_limits(
    api_key: str = Depends(verify_admin_api_key)
):
    """Manually trigger daily limits reset task."""
    try:
        from app.tasks.user import reset_all_daily_limits
        task = reset_all_daily_limits.delay()
        
        return {
            "status": "initiated",
            "task_id": task.id,
            "message": "Daily limits reset task started"
        }
    except Exception as e:
        logger.error(f"Failed to trigger reset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/trigger/send-statistics")
async def trigger_send_statistics(
    api_key: str = Depends(verify_admin_api_key)
):
    """Manually trigger usage statistics send task."""
    try:
        from app.tasks.notifications import send_usage_statistics
        task = send_usage_statistics.delay()
        
        return {
            "status": "initiated",
            "task_id": task.id,
            "message": "Statistics send task started"
        }
    except Exception as e:
        logger.error(f"Failed to trigger send: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
