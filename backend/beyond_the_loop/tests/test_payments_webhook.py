"""
Unit tests for the invoice.payment_succeeded webhook handler in
beyond_the_loop/routers/payments.py.

The handler grants Flex Credits when a paid Stripe invoice contains a line
item that references the Flex Credits product. This replaced an older
metadata-driven flow so that sales can create top-up invoices from the Stripe
dashboard by simply adding the product as a line item with any amount.

Two properties matter and are pinned down here:

  1. **Product-based detection**: only invoices with a matching line item
     grant credits, and the granted amount equals the net (pre-tax) line
     amount in EUR. Subscription-renewal invoices (no matching product) are
     no-ops.
  2. **Idempotency**: Stripe delivers webhooks at-least-once (retries,
     dashboard "resend", restarts). Duplicate deliveries of the same invoice
     must credit exactly once. Guarded by a Redis SETNX on the invoice id.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_payments_webhook.py -v
"""

import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub the heavy deps BEFORE importing the module under test.
# ---------------------------------------------------------------------------

FLEX_PRODUCT_ID = "prod_TEST_flex"
OTHER_PRODUCT_ID = "prod_TEST_subscription"


def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# In-memory Redis stand-in — models SETNX + EX semantics well enough for the
# handler's guarantees (never double-credit on the same invoice id).
class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)


_fake_redis = _FakeRedis()


class _FakeRedisModule:
    class Redis:
        @staticmethod
        def from_url(*args, **kwargs):
            return _fake_redis


_stub_module("redis", Redis=_FakeRedisModule.Redis)

# stripe: never actually contacted by the webhook handler — checkout webhook
# already verifies the signature upstream. Stub is only needed because the
# router module imports stripe at module level for the recharge endpoint.
_stub_module(
    "stripe",
    api_key=None,
    Invoice=MagicMock(),
    InvoiceItem=MagicMock(),
    PaymentMethod=MagicMock(),
    Subscription=MagicMock(),
    Webhook=MagicMock(),
    checkout=MagicMock(),
    billing_portal=MagicMock(),
    error=types.SimpleNamespace(
        SignatureVerificationError=Exception,
        CardError=Exception,
    ),
)

# open_webui.env — the router imports REDIS_URL from here.
_stub_module("open_webui.env", REDIS_URL="redis://fake", SRC_LOG_LEVELS={"MAIN": 20})

# open_webui.utils.auth — get_verified_user is imported at top level.
_stub_module("open_webui.utils.auth", get_verified_user=MagicMock())

# beyond_the_loop.socket.main — three RedisDicts are imported.
_stub_module(
    "beyond_the_loop.socket.main",
    STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE={},
    STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE={},
    STRIPE_PRODUCT_CACHE={},
)

# Companies — will be re-configured per test as needed.
_Companies = MagicMock()
_stub_module("beyond_the_loop.models.companies", Companies=_Companies)

# Users — imported at top level.
_stub_module("beyond_the_loop.models.users", Users=MagicMock())

# crm_service.
_stub_module("beyond_the_loop.services.crm_service", crm_service=MagicMock())

# payments_service — the router reads .stripe_flex_credit_product_id from the
# instance and calls is_flat_rate_plan; both need to be reachable.
_payments_service = MagicMock()
_payments_service.stripe_flex_credit_product_id = FLEX_PRODUCT_ID
_payments_service.FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS = 2000
_stub_module(
    "beyond_the_loop.services.payments_service",
    payments_service=_payments_service,
    is_flat_rate_plan=lambda plan: plan in {"free", "premium", "unlimited"},
)

# Other test modules (e.g. test_credit_service.py) install their own stub for
# beyond_the_loop.routers.payments in sys.modules. When they run before us in
# the same pytest session, that stub shadows the real router module and our
# imports resolve to a MagicMock. Force a fresh import.
sys.modules.pop("beyond_the_loop.routers.payments", None)
sys.modules.pop("beyond_the_loop.routers", None)

import beyond_the_loop.routers.payments as pr  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state():
    _fake_redis.store.clear()
    _Companies.reset_mock()
    _Companies.add_flex_credit_balance.reset_mock()
    _Companies.get_company_by_stripe_customer_id.reset_mock()
    _Companies.get_company_by_stripe_customer_id.return_value = MagicMock(id="company-1")
    yield


def _line(product_id, amount_excluding_tax=None, amount=None):
    line = {"price": {"product": product_id}}
    if amount_excluding_tax is not None:
        line["amount_excluding_tax"] = amount_excluding_tax
    if amount is not None:
        line["amount"] = amount
    return line


def _invoice(invoice_id="in_test_1", customer="cus_1", lines=None):
    return {
        "id": invoice_id,
        "customer": customer,
        "lines": {"data": lines or []},
    }


# ---------------------------------------------------------------------------
# _sum_flex_credit_line_amounts_in_cents
# ---------------------------------------------------------------------------


class TestSumFlexCreditLineAmounts:
    def test_matches_single_flex_line_using_amount_excluding_tax(self):
        invoice = _invoice(lines=[_line(FLEX_PRODUCT_ID, amount_excluding_tax=2000, amount=2380)])
        assert pr._sum_flex_credit_line_amounts_in_cents(invoice) == 2000

    def test_sums_across_multiple_flex_lines(self):
        # A dashboard-created invoice can carry several flex-credit line items.
        # We sum them all rather than crediting only the first.
        invoice = _invoice(lines=[
            _line(FLEX_PRODUCT_ID, amount_excluding_tax=1500),
            _line(FLEX_PRODUCT_ID, amount_excluding_tax=500),
        ])
        assert pr._sum_flex_credit_line_amounts_in_cents(invoice) == 2000

    def test_ignores_non_flex_product_lines(self):
        # Subscription-renewal invoices are the primary non-target case.
        invoice = _invoice(lines=[_line(OTHER_PRODUCT_ID, amount_excluding_tax=44900)])
        assert pr._sum_flex_credit_line_amounts_in_cents(invoice) == 0

    def test_mixed_invoice_credits_only_flex_lines(self):
        invoice = _invoice(lines=[
            _line(OTHER_PRODUCT_ID, amount_excluding_tax=44900),  # subscription
            _line(FLEX_PRODUCT_ID, amount_excluding_tax=5000),    # flex top-up
        ])
        assert pr._sum_flex_credit_line_amounts_in_cents(invoice) == 5000

    def test_falls_back_to_amount_when_amount_excluding_tax_missing(self):
        # Older Stripe API versions or edge cases where the field is absent.
        invoice = _invoice(lines=[_line(FLEX_PRODUCT_ID, amount=2000)])
        assert pr._sum_flex_credit_line_amounts_in_cents(invoice) == 2000

    def test_empty_invoice_returns_zero(self):
        assert pr._sum_flex_credit_line_amounts_in_cents(_invoice(lines=[])) == 0

    def test_missing_lines_field_returns_zero(self):
        assert pr._sum_flex_credit_line_amounts_in_cents({"id": "in_x"}) == 0


# ---------------------------------------------------------------------------
# handle_invoice_payment_succeeded
# ---------------------------------------------------------------------------


class TestHandleInvoicePaymentSucceeded:
    def test_grants_credits_for_flex_invoice(self):
        invoice = _invoice(
            invoice_id="in_1",
            customer="cus_1",
            lines=[_line(FLEX_PRODUCT_ID, amount_excluding_tax=2000)],
        )
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_called_once_with("company-1", 20.0)

    def test_duplicate_delivery_credits_only_once(self):
        # Stripe retries or dashboard "resend" — same event.id / invoice.id
        # arriving multiple times must not double-credit the customer.
        invoice = _invoice(
            invoice_id="in_dupe",
            lines=[_line(FLEX_PRODUCT_ID, amount_excluding_tax=5000)],
        )
        pr.handle_invoice_payment_succeeded(invoice)
        pr.handle_invoice_payment_succeeded(invoice)  # retry
        pr.handle_invoice_payment_succeeded(invoice)  # yet another retry

        _Companies.add_flex_credit_balance.assert_called_once_with("company-1", 50.0)

    def test_subscription_invoice_is_ignored(self):
        # A regular monthly subscription-renewal invoice has no matching
        # product line. Must not credit and must not consume an idempotency
        # slot (so unrelated invoice ids stay clean).
        invoice = _invoice(
            invoice_id="in_sub",
            lines=[_line(OTHER_PRODUCT_ID, amount_excluding_tax=44900)],
        )
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_not_called()
        assert _fake_redis.store == {}

    def test_no_credit_when_company_lookup_fails(self):
        # A paid flex-credit invoice for a customer not in our DB (data drift
        # or race between customer creation and payment). We log and skip
        # rather than crediting some random company.
        _Companies.get_company_by_stripe_customer_id.return_value = None
        invoice = _invoice(
            invoice_id="in_orphan",
            customer="cus_unknown",
            lines=[_line(FLEX_PRODUCT_ID, amount_excluding_tax=2000)],
        )
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_not_called()

    def test_credits_net_amount_not_gross(self):
        # Sales enters "200 EUR net" in the dashboard → invoice line is
        # 200 EUR net + tax. We must credit 200 EUR (net), not the gross total.
        invoice = _invoice(
            invoice_id="in_net",
            lines=[_line(FLEX_PRODUCT_ID, amount_excluding_tax=20000, amount=23800)],
        )
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_called_once_with("company-1", 200.0)

    def test_multiple_lines_credited_as_sum(self):
        invoice = _invoice(
            invoice_id="in_multi",
            lines=[
                _line(FLEX_PRODUCT_ID, amount_excluding_tax=1500),
                _line(FLEX_PRODUCT_ID, amount_excluding_tax=500),
            ],
        )
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_called_once_with("company-1", 20.0)

    def test_missing_invoice_id_short_circuits(self):
        # Defensive: no id means we can't idempotently guard the grant, so we
        # skip entirely rather than potentially double-crediting.
        invoice = {
            "customer": "cus_1",
            "lines": {"data": [_line(FLEX_PRODUCT_ID, amount_excluding_tax=2000)]},
        }
        pr.handle_invoice_payment_succeeded(invoice)

        _Companies.add_flex_credit_balance.assert_not_called()
