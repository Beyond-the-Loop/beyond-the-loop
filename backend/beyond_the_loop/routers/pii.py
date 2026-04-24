"""
Pre-send PII analysis endpoint.

Stateless: does NOT touch the per-chat PIISession. Used by the frontend
composer to live-highlight detected PII so the user can selectively release
individual entities (Mode B) before pressing send.

Auth gate: requires the company-wide filter to be on AND the user to have
`pii.allow_disable_in_chat` (admins bypass). Without that permission the
user has no way to act on the result, so we don't expose the analyzer.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from beyond_the_loop.pii.session import is_pii_filter_enabled
from beyond_the_loop.utils.access_control import has_permission
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


class PIIAnalyzeRequest(BaseModel):
    text: str = Field(default="")


class PIISpan(BaseModel):
    start: int
    end: int
    entity_type: str
    original: str
    score: float


class PIIAnalyzeResponse(BaseModel):
    spans: List[PIISpan]


@router.post("/analyze", response_model=PIIAnalyzeResponse)
async def analyze(form_data: PIIAnalyzeRequest, user=Depends(get_verified_user)):
    if not is_pii_filter_enabled(user.company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PII filter is disabled for this company",
        )

    if user.role != "admin" and not has_permission(
        user.id, "pii.allow_disable_in_chat"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing permission: pii.allow_disable_in_chat",
        )

    text = form_data.text or ""
    if not text.strip():
        return PIIAnalyzeResponse(spans=[])

    try:
        from beyond_the_loop.pii.service import PresidioService

        spans = [
            PIISpan(
                start=r.start,
                end=r.end,
                entity_type=r.entity_type,
                original=text[r.start : r.end],
                score=float(r.score),
            )
            for r in PresidioService.instance().analyze(text)
        ]
        return PIIAnalyzeResponse(spans=spans)
    except Exception:
        log.exception("[pii] analyze failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PII analysis failed",
        )
