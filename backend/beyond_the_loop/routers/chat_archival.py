"""
Chat Archival API Router

Provides endpoints for managing and monitoring the automated chat archival system.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_webui.utils.auth import get_current_user, get_admin_user
from beyond_the_loop.services.chat_archival_service import chat_archival_service

router = APIRouter()
log = logging.getLogger(__name__)


class ArchivalStatsResponse(BaseModel):
    """Response model for archival statistics"""
    total_chats: int
    archived_chats: int
    active_chats: int
    archival_rate: float


class ArchivalPreviewResponse(BaseModel):
    """Response model for archival preview"""
    company_id: str
    retention_days: int
    cutoff_date: str
    candidates_count: int
    candidates: list


class ArchivalResultResponse(BaseModel):
    """Response model for archival process results"""
    success: bool
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    companies_processed: int
    chats_archived: int
    chats_deleted: int
    error: Optional[str] = None


@router.get("/stats", response_model=ArchivalStatsResponse)
async def get_archival_stats(user=Depends(get_current_user)):
    """
    Get chat archival statistics for the user's company.
    
    Args:
        user: The current authenticated user
        
    Returns:
        ArchivalStatsResponse: Statistics about chat archival
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        stats = chat_archival_service.get_archival_stats(company_id)
        return ArchivalStatsResponse(**stats)
        
    except Exception as e:
        log.error(f"Error getting archival stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting archival stats: {str(e)}")


@router.get("/preview", response_model=ArchivalPreviewResponse)
async def preview_archival_candidates(user=Depends(get_admin_user)):
    """
    Preview which chats would be archived for the user's company.
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        ArchivalPreviewResponse: Preview of chats that would be archived
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        preview = chat_archival_service.preview_archival_candidates(company_id)
        return ArchivalPreviewResponse(**preview)
        
    except Exception as e:
        log.error(f"Error getting archival preview: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting archival preview: {str(e)}")


@router.post("/trigger", response_model=ArchivalResultResponse)
async def trigger_archival_process(user=Depends(get_admin_user)):
    """
    Manually trigger the chat archival process (for testing/admin purposes).
    """
    try:
        log.info(f"Manual archival process triggered by admin user: {user.email}")
        result = chat_archival_service.run_daily_archival_process()
        return ArchivalResultResponse(**result)

    except Exception as e:
        log.error(f"Error triggering archival process: {e}")
        raise HTTPException(status_code=500, detail=f"Error triggering archival process: {str(e)}")


@router.get("/global-stats", response_model=ArchivalStatsResponse)
async def get_global_archival_stats(user=Depends(get_admin_user)):
    """
    Get global chat archival statistics across all companies.
    Only available to admin users.
    
    Args:
        user: The current authenticated admin user
        
    Returns:
        ArchivalStatsResponse: Global statistics about chat archival
    """
    try:
        stats = chat_archival_service.get_archival_stats()  # No company_id = global stats
        return ArchivalStatsResponse(**stats)
        
    except Exception as e:
        log.error(f"Error getting global archival stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting global archival stats: {str(e)}")
