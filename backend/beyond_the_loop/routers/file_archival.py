"""
File Archival API Router

Provides endpoints for managing and monitoring the automated file cleanup system.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_webui.utils.auth import get_current_user, get_admin_user
from beyond_the_loop.services.file_archival_service import file_archival_service
from beyond_the_loop.scheduler import task_scheduler

router = APIRouter()
log = logging.getLogger(__name__)


class FileCleanupStatsResponse(BaseModel):
    """Response model for file cleanup statistics"""
    total_files: int
    old_files: int
    protected_files: int
    deletable_files: int
    cutoff_date: str
    threshold_days: int


class FileCleanupPreviewResponse(BaseModel):
    """Response model for file cleanup preview"""
    company_id: Optional[str]
    cutoff_date: str
    threshold_days: int
    total_old_files: int
    protected_count: int
    candidates_count: int
    candidates: list


class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status"""
    running: bool
    jobs: list


class FileCleanupResultResponse(BaseModel):
    """Response model for file cleanup process results"""
    success: bool
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    companies_processed: int
    files_deleted: int
    files_protected: int
    error: Optional[str] = None


@router.get("/stats", response_model=FileCleanupStatsResponse)
async def get_file_cleanup_stats(user=Depends(get_current_user)):
    """
    Get file cleanup statistics for the user's company.
    
    Args:
        user: The current authenticated user
        
    Returns:
        FileCleanupStatsResponse: Statistics about file cleanup
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        stats = file_archival_service.get_cleanup_stats(company_id)
        return FileCleanupStatsResponse(**stats)
        
    except Exception as e:
        log.error(f"Error getting file cleanup stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting file cleanup stats: {str(e)}")


@router.get("/preview", response_model=FileCleanupPreviewResponse)
async def preview_file_cleanup_candidates(user=Depends(get_admin_user)):
    """
    Preview which files would be deleted for the user's company.
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        FileCleanupPreviewResponse: Preview of files that would be deleted
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        preview = file_archival_service.preview_cleanup_candidates(company_id)
        return FileCleanupPreviewResponse(**preview)
        
    except Exception as e:
        log.error(f"Error getting file cleanup preview: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting file cleanup preview: {str(e)}")


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(user=Depends(get_admin_user)):
    """
    Get the current status of the task scheduler.
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        SchedulerStatusResponse: Current scheduler status and job information
    """
    try:
        status = task_scheduler.get_scheduler_status()
        return SchedulerStatusResponse(**status)
        
    except Exception as e:
        log.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting scheduler status: {str(e)}")


@router.post("/trigger", response_model=FileCleanupResultResponse)
async def trigger_file_cleanup_process(user=Depends(get_admin_user)):
    """
    Manually trigger the file cleanup process (for testing/admin purposes).
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        FileCleanupResultResponse: Results of the file cleanup process
    """
    try:
        log.info(f"Manual file cleanup process triggered by admin user: {user.email}")
        result = task_scheduler.trigger_file_cleanup_now()
        return FileCleanupResultResponse(**result)
        
    except Exception as e:
        log.error(f"Error triggering file cleanup process: {e}")
        raise HTTPException(status_code=500, detail=f"Error triggering file cleanup process: {str(e)}")


@router.get("/global-stats", response_model=FileCleanupStatsResponse)
async def get_global_file_cleanup_stats(user=Depends(get_admin_user)):
    """
    Get global file cleanup statistics across all companies.
    Only available to admin users.
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        FileCleanupStatsResponse: Global statistics about file cleanup
    """
    try:
        stats = file_archival_service.get_cleanup_stats()  # No company_id = global stats
        return FileCleanupStatsResponse(**stats)
        
    except Exception as e:
        log.error(f"Error getting global file cleanup stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting global file cleanup stats: {str(e)}")
