"""
Pre-send PII analysis endpoint.

Stateless: does NOT touch the per-chat PIISession. Used by the frontend
composer to live-highlight detected PII so the user can see what will be
anonymized before sending. Users with `pii.allow_disable_in_chat` can also
selectively release individual entities (Mode B); users without it just see
the highlights — release/disable is gated in the UI and re-enforced when the
chat request is processed.

Auth gate: only requires the company-wide filter to be on. The view-only
case is intentionally allowed so non-privileged users get the same live
preview the privileged ones do.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from beyond_the_loop.pii.session import is_pii_filter_enabled
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
