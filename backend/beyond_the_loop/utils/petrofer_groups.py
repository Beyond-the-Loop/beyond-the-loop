"""
Hardcoded Petrofer-only signup group auto-assignment.

Called from all three signup entry points and from the one-off backfill
script. No-op for any user that is not in the Petrofer company or whose
email is not present in the static mapping.
"""
from __future__ import annotations

import logging
import time

from open_webui.internal.db import get_db
from beyond_the_loop.data.petrofer_group_assignments import (
    EMAIL_TO_GROUP_IDS,
    PETROFER_COMPANY_ID,
)
from beyond_the_loop.models.groups import Group

log = logging.getLogger(__name__)


def assign_petrofer_groups_if_applicable(user) -> None:
    """Idempotent. Never raises. Safe to call from any signup path."""
    if getattr(user, "company_id", None) != PETROFER_COMPANY_ID:
        return

    email_key = (user.email or "").strip().lower()
    group_ids = EMAIL_TO_GROUP_IDS.get(email_key)
    if not group_ids:
        return

    # Outer try/except so the helper truly never raises — this also covers
    # the possibility that get_db().__exit__ re-raises during teardown.
    try:
        with get_db() as db:
            for group_id in group_ids:
                try:
                    group = db.query(Group).filter_by(id=group_id).first()
                    if group is None:
                        log.warning(
                            "assign_petrofer_groups: group %s not found (skipping)",
                            group_id,
                        )
                        continue
                    current = list(group.user_ids or [])
                    if user.id in current:
                        continue
                    current.append(user.id)
                    group.user_ids = current
                    group.updated_at = int(time.time())
                except Exception:
                    log.exception(
                        "assign_petrofer_groups: failed to assign user %s to group %s",
                        user.id,
                        group_id,
                    )
            try:
                db.commit()
            except Exception:
                log.exception("assign_petrofer_groups: commit failed")
    except Exception:
        log.exception(
            "assign_petrofer_groups: outer session failure for user %s",
            getattr(user, "id", "<unknown>"),
        )
