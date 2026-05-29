"""
One-off cleanup: recompute ``next_credit_charge_check`` for all paid companies
based on their Stripe subscription's billing-cycle anchor.

Background
----------
A pre-7c8b60d3d webhook bug added 1 month to the existing
``next_credit_charge_check`` value on every trivial Stripe event
(``customer.subscription.updated`` fires for many reasons: metadata edits,
default-payment-method changes, cancel-at-period-end toggles, …). Each fire
pushed the date one more month into the future — so an active customer's
date could drift arbitrarily far. The fix in 7c8b60d3d only set the date
correctly going forward; existing drifted values stay broken until cleaned up
by this script.

What this script does
---------------------
For every company that:
  * has a Stripe customer id, AND
  * has an active or trialing subscription on a paid plan (not free/premium/
    unlimited)

…it computes the expected ``next_credit_charge_check`` as the next occurrence
of the Stripe ``billing_cycle_anchor`` day-of-month (and time-of-day) after
now. If the DB value differs, the company is reported (and optionally
updated).

Usage
-----
Default is dry-run::

    PYTHONPATH=backend backend/venv/bin/python -m beyond_the_loop.scripts.recompute_next_credit_charge_check

Apply (writes to DB)::

    PYTHONPATH=backend backend/venv/bin/python -m beyond_the_loop.scripts.recompute_next_credit_charge_check --apply

Apply but only first N rows (gradual rollout)::

    PYTHONPATH=backend backend/venv/bin/python -m beyond_the_loop.scripts.recompute_next_credit_charge_check --apply --limit 5
"""

import argparse
import logging
import sys
from datetime import datetime

import stripe

# Pre-load every model module that participates in Company's SQLAlchemy
# relationships so the mapper can resolve string-based targets like "Domain".
# Without these imports, ``Companies.get_all()`` raises a mapper-init error
# (and swallows it, returning None).
import beyond_the_loop.models.users  # noqa: F401
import beyond_the_loop.models.companies  # noqa: F401
import beyond_the_loop.models.domains  # noqa: F401
import beyond_the_loop.models.models  # noqa: F401
import beyond_the_loop.models.prompts  # noqa: F401
from beyond_the_loop.models.models import user_model_bookmark  # noqa: F401
from beyond_the_loop.models.prompts import user_prompt_bookmark  # noqa: F401

from beyond_the_loop.models.companies import Companies
from beyond_the_loop.services.payments_service import (
    _next_monthly_anchor_after,
    payments_service,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


FLAT_RATE_PLANS = {"free", "premium", "unlimited"}


def _fetch_stripe_subscription(company, status):
    """Return the (only) Stripe subscription dict matching ``status`` for the
    company, or ``None`` if there is none. Status is ``"active"`` or
    ``"trialing"``.
    """
    result = stripe.Subscription.list(
        customer=company.stripe_customer_id,
        status=status,
        limit=1,
    )
    data = result.get("data", [])
    return data[0] if data else None


def _expected_next_check(subscription, now_dt):
    """Compute the expected ``next_credit_charge_check`` datetime from a Stripe
    subscription. Returns ``(expected_dt, anchor_dt)`` or raises on missing
    data.
    """
    anchor_ts = subscription.get("billing_cycle_anchor") or subscription.get("start_date")
    if not anchor_ts:
        raise ValueError("subscription has no billing_cycle_anchor or start_date")
    anchor_dt = datetime.fromtimestamp(anchor_ts)
    return _next_monthly_anchor_after(anchor_dt, now_dt), anchor_dt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Actually write updates (default: dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="In apply mode, only update the first N drifted companies")
    args = parser.parse_args()

    dry_run = not args.apply
    log.info(f"=== Mode: {'DRY-RUN' if dry_run else 'APPLY'} ===")

    companies = Companies.get_all()
    if companies is None:
        log.error("Companies.get_all() returned None — see error above (likely a DB or mapper issue).")
        return 1
    now_dt = datetime.now()

    correct = 0
    needs_update = []  # list of (company, current_ts, expected_dt, anchor_dt)
    skipped = []       # list of (company, reason)
    errors = []        # list of (company, reason)

    for company in companies:
        if not company.stripe_customer_id:
            skipped.append((company, "no stripe_customer_id"))
            continue

        try:
            subscription_info = payments_service.get_subscription(company.id)
        except Exception as e:
            errors.append((company, f"get_subscription failed: {e}"))
            continue

        plan = subscription_info.get("plan")
        if plan in FLAT_RATE_PLANS:
            skipped.append((company, f"plan={plan}"))
            continue

        is_trial = subscription_info.get("is_trial", False)
        status = subscription_info.get("status")
        if not is_trial and status != "active":
            skipped.append((company, f"subscription inactive (status={status})"))
            continue

        try:
            stripe_sub = _fetch_stripe_subscription(
                company, status="trialing" if is_trial else "active"
            )
        except Exception as e:
            errors.append((company, f"stripe fetch failed: {e}"))
            continue
        if not stripe_sub:
            errors.append((company, "stripe says no matching subscription"))
            continue

        try:
            expected_dt, anchor_dt = _expected_next_check(stripe_sub, now_dt)
        except Exception as e:
            errors.append((company, f"compute failed: {e}"))
            continue

        current_ts = company.next_credit_charge_check

        # "Correct" = same calendar date as expected. Sub-day differences are
        # webhook-latency artifacts (old _set_..._one_month_from_now used
        # ``datetime.now()`` at webhook-receive time instead of the anchor
        # time, leaving a few seconds/minutes of drift). The cron only checks
        # ``<= now`` once a day, so anything within the same day is functionally
        # identical and not worth updating.
        if current_ts is not None and (
            datetime.fromtimestamp(current_ts).date() == expected_dt.date()
        ):
            correct += 1
        else:
            needs_update.append((company, current_ts, expected_dt, anchor_dt))

    # Apply (limited optionally)
    updates_applied = 0
    if not dry_run:
        to_update = needs_update if args.limit is None else needs_update[: args.limit]
        if args.limit is not None and args.limit < len(needs_update):
            log.info(f"Limiting writes to first {args.limit} of {len(needs_update)} drifted companies.")
        for company, _current, expected_dt, _anchor in to_update:
            try:
                Companies.update_company_by_id(
                    company.id,
                    {"next_credit_charge_check": expected_dt.timestamp()},
                )
                updates_applied += 1
            except Exception as e:
                errors.append((company, f"update failed: {e}"))

    # Report
    log.info("")
    log.info("=" * 70)
    scanned = correct + len(needs_update)
    log.info(f"Scanned (paid + active/trialing): {scanned}")
    log.info(f"  Exactly correct:                {correct}")
    log.info(f"  Needs update:                   {len(needs_update)}")

    for company, current, expected, anchor in needs_update[:30]:
        current_str = (
            datetime.fromtimestamp(current).strftime("%Y-%m-%d %H:%M:%S")
            if current
            else "NULL"
        )
        log.info(
            f"    - {company.name[:30]:30s} (id={company.id[:8]}) "
            f"DB: {current_str:19s} → {expected.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(anchor day={anchor.day})"
        )
    if len(needs_update) > 30:
        log.info(f"    ... and {len(needs_update) - 30} more")

    log.info(f"Skipped:                          {len(skipped)}")
    for company, reason in skipped[:20]:
        log.info(f"    - {company.name[:30]:30s} (id={company.id[:8]}): {reason}")
    if len(skipped) > 20:
        log.info(f"    ... and {len(skipped) - 20} more skipped")

    log.info(f"Errors:                           {len(errors)}")
    for company, err in errors[:10]:
        log.info(f"    - {company.name[:30]:30s} (id={company.id[:8]}): {err}")
    if len(errors) > 10:
        log.info(f"    ... and {len(errors) - 10} more errors")

    if dry_run:
        log.info("")
        log.info("Dry run — no writes performed. Pass --apply to commit.")
    else:
        log.info(f"Updates applied:                  {updates_applied}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
