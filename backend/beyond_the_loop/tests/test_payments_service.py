"""
Unit tests for the pure helpers in beyond_the_loop/services/payments_service.py.

Currently covers ``_next_monthly_anchor_after`` which determines the next
``next_credit_charge_check`` value from a Stripe billing-cycle anchor — used
by both the subscription webhook and the cleanup script in
``scripts/recompute_next_credit_charge_check.py``. Drift here means companies
get billed at the wrong time or never, so it's worth pinning down with tests.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_payments_service.py -v
"""

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub the heavy deps BEFORE importing the module under test.
# ---------------------------------------------------------------------------

def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_stub_module("stripe", api_key=None, Subscription=MagicMock(), Webhook=MagicMock(),
             PaymentMethod=MagicMock(), error=types.SimpleNamespace(SignatureVerificationError=Exception))
_stub_module("beyond_the_loop.models.companies", Companies=MagicMock())
_stub_module("beyond_the_loop.models.users", Users=MagicMock())
_stub_module("beyond_the_loop.services.crm_service", crm_service=MagicMock())
_stub_module(
    "beyond_the_loop.socket.main",
    STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE={},
    STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE={},
    STRIPE_PRODUCT_CACHE={},
)

import beyond_the_loop.services.payments_service as ps  # noqa: E402


# ---------------------------------------------------------------------------
# _next_monthly_anchor_after
# ---------------------------------------------------------------------------


class TestNextMonthlyAnchorAfter:
    """The pivot of next_credit_charge_check calculation: given an anchor
    (e.g. subscription start at 2026-04-02 14:30) and a current moment, find
    the next datetime at the anchor day-of-month and time-of-day.
    """

    def test_anchor_day_later_this_month_returns_this_month(self):
        # Anchor: day 15 at 10:00. Today: day 5. Next check should be the 15th of this month.
        anchor = datetime(2026, 1, 15, 10, 0, 0)
        now = datetime(2026, 5, 5, 8, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        assert result == datetime(2026, 5, 15, 10, 0, 0)

    def test_anchor_day_already_passed_this_month_returns_next_month(self):
        # Anchor: day 5. Today: day 28. Next check should be the 5th of next month.
        anchor = datetime(2026, 1, 5, 14, 30, 0)
        now = datetime(2026, 5, 28, 8, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        assert result == datetime(2026, 6, 5, 14, 30, 0)

    def test_anchor_day_today_but_time_already_passed_returns_next_month(self):
        # Anchor: day 10 at 09:00. Today: day 10 at 15:00. The 10:00 slot has passed.
        anchor = datetime(2026, 1, 10, 9, 0, 0)
        now = datetime(2026, 5, 10, 15, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        assert result == datetime(2026, 6, 10, 9, 0, 0)

    def test_anchor_day_today_but_time_still_upcoming_returns_today(self):
        # Anchor: day 10 at 22:00. Today: day 10 at 15:00. The 22:00 slot is still upcoming.
        anchor = datetime(2026, 1, 10, 22, 0, 0)
        now = datetime(2026, 5, 10, 15, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        assert result == datetime(2026, 5, 10, 22, 0, 0)

    def test_anchor_day_31_clamps_to_february_last_day(self):
        # Anchor day 31. Now late Jan. Next 31st is in March (Jan 31 is passed),
        # but the immediate candidate via relativedelta(day=31) on Feb clamps
        # to Feb 28 (or 29 in leap years).
        anchor = datetime(2026, 7, 31, 12, 0, 0)
        now = datetime(2026, 2, 1, 0, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        # 2026 is not a leap year → Feb 28
        assert result == datetime(2026, 2, 28, 12, 0, 0)

    def test_anchor_day_31_in_leap_year_february(self):
        anchor = datetime(2024, 7, 31, 12, 0, 0)
        now = datetime(2024, 2, 1, 0, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        # 2024 is a leap year → Feb 29
        assert result == datetime(2024, 2, 29, 12, 0, 0)

    def test_anchor_in_the_future_still_returns_next_anchor_after_now(self):
        # Edge case from the cleanup script's perspective: anchor is in the
        # future (Stripe subscription scheduled to start later). The helper
        # should still return the next anchor-day occurrence after now.
        anchor = datetime(2030, 8, 7, 9, 0, 0)
        now = datetime(2026, 5, 28, 15, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        # The 7th of June 2026 is the next 7th after May 28.
        assert result == datetime(2026, 6, 7, 9, 0, 0)

    def test_anchor_year_in_past_does_not_affect_calculation(self):
        # Demonstrates that anchor's year/month are ignored — only day/time-of-day matter.
        old_anchor = datetime(2020, 3, 2, 14, 30, 0)
        now = datetime(2026, 5, 28, 12, 0, 0)
        result = ps._next_monthly_anchor_after(old_anchor, now)
        # Next 2nd after May 28 = June 2.
        assert result == datetime(2026, 6, 2, 14, 30, 0)

    def test_anchor_seconds_preserved(self):
        anchor = datetime(2026, 1, 15, 10, 30, 45)
        now = datetime(2026, 5, 5, 8, 0, 0)
        result = ps._next_monthly_anchor_after(anchor, now)
        assert result == datetime(2026, 5, 15, 10, 30, 45)


# ---------------------------------------------------------------------------
# _get_custom_seats
# ---------------------------------------------------------------------------


class TestGetCustomSeats:
    """Reads custom_seats from Stripe subscription metadata. Returns a positive
    int or None. Malformed non-empty values log a warning and return None so
    callers fall back to the plan's default seats value.
    """

    def test_returns_int_for_positive_string(self):
        sub = {"metadata": {"custom_seats": "200"}}
        assert ps._get_custom_seats(sub) == 200

    def test_returns_int_for_large_value(self):
        sub = {"metadata": {"custom_seats": "1000"}}
        assert ps._get_custom_seats(sub) == 1000

    def test_returns_none_when_metadata_key_missing(self):
        sub = {"metadata": {"other_key": "x"}}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_when_metadata_dict_missing(self):
        sub = {}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_when_metadata_is_none(self):
        sub = {"metadata": None}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_for_empty_string(self):
        sub = {"metadata": {"custom_seats": ""}}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_for_zero(self):
        sub = {"metadata": {"custom_seats": "0"}}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_for_negative(self):
        sub = {"metadata": {"custom_seats": "-5"}}
        assert ps._get_custom_seats(sub) is None

    def test_returns_none_for_non_numeric(self, caplog):
        sub = {"metadata": {"custom_seats": "abc"}}
        with caplog.at_level("WARNING"):
            assert ps._get_custom_seats(sub) is None
        assert any("custom_seats" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _get_custom_credit_amount
# ---------------------------------------------------------------------------


class TestGetCustomCreditAmount:
    """Reads custom_credit_amount from Stripe subscription metadata. Returns a
    positive int or None. Harmonizes previous inline handling that treated
    "0" and malformed values inconsistently across get_subscription and the
    subscription webhook.
    """

    def test_returns_int_for_positive_string(self):
        sub = {"metadata": {"custom_credit_amount": "500"}}
        assert ps._get_custom_credit_amount(sub) == 500

    def test_returns_none_when_metadata_key_missing(self):
        sub = {"metadata": {"other_key": "x"}}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_when_metadata_dict_missing(self):
        sub = {}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_when_metadata_is_none(self):
        sub = {"metadata": None}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_for_empty_string(self):
        sub = {"metadata": {"custom_credit_amount": ""}}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_for_zero(self):
        sub = {"metadata": {"custom_credit_amount": "0"}}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_for_negative(self):
        sub = {"metadata": {"custom_credit_amount": "-10"}}
        assert ps._get_custom_credit_amount(sub) is None

    def test_returns_none_for_non_numeric(self, caplog):
        sub = {"metadata": {"custom_credit_amount": "abc"}}
        with caplog.at_level("WARNING"):
            assert ps._get_custom_credit_amount(sub) is None
        assert any("custom_credit_amount" in r.message for r in caplog.records)
