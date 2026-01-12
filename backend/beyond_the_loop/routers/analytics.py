from fastapi import HTTPException, Depends
from fastapi.params import Query

from beyond_the_loop.models.users import get_users_by_company
from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_db
from beyond_the_loop.models.models import Model

from fastapi import APIRouter, status

import logging

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from beyond_the_loop.services.analytics_service import AnalyticsService
from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

@router.get("/top-models")
async def get_top_models(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
    user=Depends(get_verified_user)
):
    """
    Returns the top 5 models based on usage for the user's company within the specified date range.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_top_models_by_company(user.company_id, start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top models: {e}")


@router.get("/top-users")
async def get_top_users(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
    user=Depends(get_verified_user)
):
    """
    Returns the top users based on different metrics (credits used, messages, assistants created)
    for the user's company and within a specified date range.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_top_users_by_company(user.company_id, start_date, end_date)
    except ValueError as ve:
        # Add more detailed error information
        log.error(f"ValueError in get_top_users: {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD. Error: {ve}")
    except Exception as e:
        # Log the specific error
        log.error(f"Error in get_top_users: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching top users: {e}")


@router.get("/stats/total-billing")
async def get_total_billing(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format (optional)"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format (optional)"),
    user=Depends(get_verified_user)
):
    """
    Returns total billing data for the last 12 months or within a specified time frame,
    filtered by the user's company.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.calculate_credit_consumption_by_company(company_id=user.company_id, start_date=start_date, end_date=end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching billing stats: {e}")

@router.get("/stats/total-messages")
async def get_total_messages(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format (optional)"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format (optional)"),
    user=Depends(get_verified_user)
):
    """
    Returns total number of completions for the last 12 months or within a specified time frame,
    filtered by the user's company.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_total_messages_by_company(company_id=user.company_id, start_date=start_date, end_date=end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching message stats: {e}")


@router.get("/stats/total-chats")
async def get_total_chats(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format (optional)"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format (optional)"),
    user=Depends(get_verified_user)
):
    """
    Returns total number of unique chats for the last 12 months or within a specified time frame,
    filtered by the user's company.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_total_chats_by_company(company_id=user.company_id, start_date=start_date, end_date=end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat stats: {e}")


@router.get("/stats/saved-time-in-seconds")
async def get_saved_time_in_seconds(
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format (optional)"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format (optional)"),
    user=Depends(get_verified_user)
):
    """
    Returns total saved time in seconds for the last 12 months or within a specified time frame,
    filtered by the user's completions.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_saved_time_in_seconds_by_company(company_id=user.company_id, start_date=start_date, end_date=end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching saved time stats: {e}")


@router.get("/stats/total-users")
async def get_total_users(user=Depends(get_verified_user)):
    """
    Returns the total number of users that have an account for the user's company.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return {"total_users": len(get_users_by_company(user.company_id))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching total users: {e}")


@router.get("/stats/adoption-rate")
async def get_adoption_rate(user=Depends(get_verified_user)):
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.calculate_adoption_rate_by_company(user.company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating adoption rate: {e}")


@router.get("/stats/power-users")
async def get_power_users(user=Depends(get_verified_user)):
    """
    Returns users for the user's company that wrote more than 400 messages 
    in the last 30 days.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        return AnalyticsService.get_power_users_by_company(user.company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching power users: {e}")


@router.get("/stats/total-assistants")
async def get_total_assistants(user=Depends(get_verified_user)):
    """
    Returns the total number of assistants (models) that are available for the user's company.
    """
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    try:
        with get_db() as db:
            # Query models that belong to the user's company
            total_assistants = db.query(Model).filter(
                Model.company_id == user.company_id,
                Model.base_model_id != None
            ).count()
            
            return {"total_assistants": total_assistants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching total assistants: {e}")
