"""
Unit tests for budget-mail-flag re-arming inside
``Companies.add_flex_credit_balance``.

Background: the 80%/100% warning mails are gated on
``budget_mail_80_sent`` / ``budget_mail_100_sent`` flags that flip True
when the warning fires. They are otherwise only reset on the monthly
billing-period roll-over or on a Stripe subscription reset. If a company
drops to 0, gets auto-recharged, and burns through the recharge a second
time in the same period, the flags would stay sticky and no second
warning would go out. ``add_flex_credit_balance`` now re-arms them when
the new total crosses back above the warning thresholds.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_companies_model.py -v
"""

import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# Stub heavy / circular deps before importing the module under test.
_stub_module(
    "open_webui.internal.db",
    get_db=MagicMock(),
    Base=type("Base", (), {"metadata": MagicMock()}),
)

import beyond_the_loop.models.companies as companies_module  # noqa: E402


@contextmanager
def _fake_get_db(session):
    """Context manager replacement so ``with get_db() as db: ...`` yields
    our mock session."""
    yield session


def _make_company(*, credit_balance, flex_credit_balance,
                  budget_mail_80_sent, budget_mail_100_sent):
    company = MagicMock()
    company.credit_balance = credit_balance
    company.flex_credit_balance = flex_credit_balance
    company.budget_mail_80_sent = budget_mail_80_sent
    company.budget_mail_100_sent = budget_mail_100_sent
    return company


def _patch_db_with_company(company):
    """Patch ``companies_module.get_db`` so the model method sees a mock
    session that returns ``company`` for the .first() lookup."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = company
    return patch.object(
        companies_module, "get_db",
        lambda: _fake_get_db(db),
    )


class TestAddFlexCreditBalanceResetsBudgetMailFlags:
    """The reset is the whole point of the function's added behavior."""

    def test_resets_both_flags_when_total_climbs_above_80pct_threshold(self):
        # Starter-style: threshold = 1 EUR, recharge of 20 lifts total well above.
        company = _make_company(
            credit_balance=0,
            flex_credit_balance=0,
            budget_mail_80_sent=True,
            budget_mail_100_sent=True,
        )
        with _patch_db_with_company(company), \
             patch.object(companies_module.CompanyTable,
                          "get_eighty_percent_credit_limit",
                          return_value=1.0):
            ok = companies_module.Companies.add_flex_credit_balance("co_1", 20.0)

        assert ok is True
        assert company.flex_credit_balance == 20.0
        assert company.budget_mail_80_sent is False
        assert company.budget_mail_100_sent is False

    def test_resets_only_100_flag_when_total_above_zero_but_below_80pct(self):
        # Enterprise-style: threshold = 90 EUR. A single 20 EUR recharge lifts
        # the user off zero but not above the warning threshold.
        company = _make_company(
            credit_balance=0,
            flex_credit_balance=0,
            budget_mail_80_sent=True,
            budget_mail_100_sent=True,
        )
        with _patch_db_with_company(company), \
             patch.object(companies_module.CompanyTable,
                          "get_eighty_percent_credit_limit",
                          return_value=90.0):
            companies_module.Companies.add_flex_credit_balance("co_1", 20.0)

        assert company.budget_mail_80_sent is True  # still warning territory
        assert company.budget_mail_100_sent is False  # no longer empty

    def test_initialises_flex_balance_when_none(self):
        # First-ever flex top-up: column was NULL, must become the recharge
        # amount (not crash on ``None += float``).
        company = _make_company(
            credit_balance=5.0,
            flex_credit_balance=None,
            budget_mail_80_sent=False,
            budget_mail_100_sent=False,
        )
        with _patch_db_with_company(company), \
             patch.object(companies_module.CompanyTable,
                          "get_eighty_percent_credit_limit",
                          return_value=1.0):
            companies_module.Companies.add_flex_credit_balance("co_1", 20.0)

        assert company.flex_credit_balance == 20.0

    def test_returns_false_when_company_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(companies_module, "get_db",
                          lambda: _fake_get_db(db)), \
             patch.object(companies_module.CompanyTable,
                          "get_eighty_percent_credit_limit",
                          return_value=1.0):
            ok = companies_module.Companies.add_flex_credit_balance(
                "missing", 20.0)

        assert ok is False

    def test_does_not_touch_already_false_flags(self):
        # If both flags are already False (e.g. fresh billing period),
        # the function should leave them alone.
        company = _make_company(
            credit_balance=50.0,
            flex_credit_balance=10.0,
            budget_mail_80_sent=False,
            budget_mail_100_sent=False,
        )
        with _patch_db_with_company(company), \
             patch.object(companies_module.CompanyTable,
                          "get_eighty_percent_credit_limit",
                          return_value=1.0):
            companies_module.Companies.add_flex_credit_balance("co_1", 20.0)

        assert company.budget_mail_80_sent is False
        assert company.budget_mail_100_sent is False
        assert company.flex_credit_balance == 30.0
