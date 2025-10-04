import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from beyond_the_loop.services.intercom_service import intercom_service


router = APIRouter()
log = logging.getLogger(__name__)


class IntercomTokenResponse(BaseModel):
    token: str


@router.get("/token", response_model=IntercomTokenResponse)
async def token(user=Depends(get_verified_user)):
    return IntercomTokenResponse(token=intercom_service.generate_user_token(user))
