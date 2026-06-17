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

import asyncio
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from beyond_the_loop.pii.session import is_pii_filter_enabled
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

# Per-process FIFO queue for live-preview analyzes. Combined with the
# per-user supersession check below, stale requests release the slot in
# microseconds without doing any transformer work — only the latest typed
# version of each user's text actually goes through the model.
# Sized to 1 deliberately — the actual CPU budget lives in service.py; this
# is just the entry point that picks the freshest waiter.
_LIVE_PREVIEW_SEM = asyncio.Semaphore(1)

# Latest request sequence per user. Each new analyze bumps the counter and
# remembers its own seq; when its turn comes, it bails if a newer one has
# bumped past it. Cheaper and more reliable than detecting HTTP-level client
# disconnects through proxies.
_LATEST_SEQ: Dict[str, int] = {}
_LATEST_LOCK = asyncio.Lock()


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
async def analyze(
    form_data: PIIAnalyzeRequest,
    user=Depends(get_verified_user),
):
    if not is_pii_filter_enabled(user.company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PII filter is disabled for this company",
        )

    text = form_data.text or ""
    if not text.strip():
        return PIIAnalyzeResponse(spans=[])

    # Claim a seq for this request before queueing. Anyone arriving after us
    # for the same user will get a higher seq and supersede.
    async with _LATEST_LOCK:
        my_seq = _LATEST_SEQ.get(user.id, 0) + 1
        _LATEST_SEQ[user.id] = my_seq

    async with _LIVE_PREVIEW_SEM:
        # Our turn — skip the transformer if we've already been superseded.
        if _LATEST_SEQ.get(user.id) != my_seq:
            return PIIAnalyzeResponse(spans=[])

        try:
            from beyond_the_loop.pii.service import PresidioService

            # to_thread keeps the event loop responsive while the blocking
            # analyze runs (it still goes through service.py's own
            # BoundedSemaphore for the process-wide CPU cap).
            raw = await asyncio.to_thread(
                PresidioService.instance().analyze, text
            )
            spans = [
                PIISpan(
                    start=r.start,
                    end=r.end,
                    entity_type=r.entity_type,
                    original=text[r.start : r.end],
                    score=float(r.score),
                )
                for r in raw
            ]
            return PIIAnalyzeResponse(spans=spans)
        except Exception:
            log.exception("[pii] analyze failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PII analysis failed",
            )
