"""
Unit tests for beyond_the_loop/services/credit_service.py.

Covers ``record_completion`` which is the central choke point for the
pricing/completion/analytics flow: every chat-completion, agent prompt and
task prompt that flows through the system goes through this function. The
behavior matrix matters because:

  - Pay-as-you-go callers must actually have credits subtracted.
  - Flat-rate plans (free / premium / unlimited) must NOT have credits
    subtracted, but the cost must still be recorded on the Completion row
    (used for internal margin analytics).
  - Agent/task prompts must ALSO record the cost but never subtract, so we
    don't bill internal LLM calls to the customer.
  - The Completion row is always inserted, regardless of plan or origin.

All external dependencies (DB, LiteLLM, Stripe, Companies, etc.) are stubbed
so the tests run without a server, DB or the full pip environment.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_credit_service.py -v
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub every heavy dependency BEFORE the module under test is imported.
# ---------------------------------------------------------------------------

def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# litellm stub — completion_cost returns 0.01 USD by default; tests override per-case
_litellm = _stub_module(
    "litellm",
    completion_cost=MagicMock(return_value=0.01),
    model_cost={},
)

# stripe stub
_stub_module("stripe", PaymentMethod=MagicMock())

# open_webui.env stub
_stub_module("open_webui.env", SRC_LOG_LEVELS={"MAIN": 20})

# beyond_the_loop.models.users stub
class _UserModel:
    def __init__(self, id="user-1", company_id="company-1", email="u@example.com", first_name="Alice"):
        self.id = id
        self.company_id = company_id
        self.email = email
        self.first_name = first_name


_Users = MagicMock()
_stub_module("beyond_the_loop.models.users", UserModel=_UserModel, Users=_Users)

# beyond_the_loop.models.companies stub — Companies methods will be patched per test
_Companies = MagicMock()
_Companies.get_base_credit_balance = MagicMock(return_value=1000.0)
_Companies.get_credit_balance = MagicMock(return_value=1000.0)
_Companies.get_eighty_percent_credit_limit = MagicMock(return_value=200.0)
_Companies.get_auto_recharge = MagicMock(return_value=False)
_Companies.get_company_by_id = MagicMock(return_value=MagicMock(stripe_customer_id="cus_1", budget_mail_80_sent=True))
_Companies.subtract_credit_balance = MagicMock()
_Companies.update_company_by_id = MagicMock()
_stub_module("beyond_the_loop.models.companies", Companies=_Companies)

# beyond_the_loop.services.email_service stub
_stub_module("beyond_the_loop.services.email_service", EmailService=MagicMock)

# beyond_the_loop.config stub
_stub_module(
    "beyond_the_loop.config",
    LITELLM_MODEL_CONFIG={},
    LITELLM_MODEL_MAP={"GPT-4o": "azure/gpt-4o"},
)

# beyond_the_loop.routers.payments stub (get_subscription is imported at top level)
_stub_module("beyond_the_loop.routers.payments", get_subscription=MagicMock())

# beyond_the_loop.services.payments_service stub (is_flat_rate_plan is imported at top level)
_stub_module(
    "beyond_the_loop.services.payments_service",
    is_flat_rate_plan=lambda plan: plan in {"free", "premium", "unlimited"},
    FLAT_RATE_PLANS=frozenset({"free", "premium", "unlimited"}),
)

# beyond_the_loop.models.completions stub — replace insert_new_completion with a spy
_Completions = MagicMock()
_Completions.insert_new_completion = MagicMock()
_stub_module("beyond_the_loop.models.completions", Completions=_Completions)

# Now it is safe to import the module under test
import beyond_the_loop.services.credit_service as cs  # noqa: E402

# Force the credit_service module to use our litellm stub even if the real
# litellm was already imported by a pytest plugin or another test module.
cs.litellm = _litellm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all spies and side_effects between tests so state doesn't leak."""
    _Completions.insert_new_completion.reset_mock()
    _Companies.subtract_credit_balance.reset_mock()
    _Companies.get_base_credit_balance.return_value = 1000.0
    _Companies.get_credit_balance.return_value = 1000.0
    _Companies.get_eighty_percent_credit_limit.return_value = 200.0
    _Companies.get_auto_recharge.return_value = False
    # reset_mock(side_effect=True) is required — plain reset_mock() does not
    # clear side_effects set by an earlier test (e.g. the exception-swallowing
    # test below leaks its Exception side_effect otherwise).
    _litellm.completion_cost.reset_mock(side_effect=True, return_value=True)
    _litellm.completion_cost.return_value = 0.01
    yield


@pytest.fixture
def user():
    return _UserModel()


@pytest.fixture
def usage_response():
    # OpenAI chat.completions-shaped response with usage info — what the litellm
    # streaming/non-streaming code paths feed into record_completion.
    return {
        "model": "GPT-4o",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


# ---------------------------------------------------------------------------
# _compute_credit_cost
# ---------------------------------------------------------------------------


class TestComputeCreditCost:
    """The pure cost helper. No side effects — does not subtract anything."""

    def test_applies_profit_margin_and_eur_conversion(self, usage_response):
        _litellm.completion_cost.return_value = 1.0  # 1 USD
        cost = cs.CreditService._compute_credit_cost(usage_response)
        # 1 USD * 1.25 margin * 0.9 EUR/USD = 1.125
        assert cost == pytest.approx(1.125)

    def test_swallows_litellm_errors_and_returns_zero(self, usage_response):
        _litellm.completion_cost.side_effect = Exception("unknown model")
        cost = cs.CreditService._compute_credit_cost(usage_response)
        assert cost == 0.0

    def test_perplexity_search_query_cost_added(self, usage_response):
        usage_response["model"] = "Perplexity Sonar"
        _litellm.completion_cost.return_value = 0.0
        with patch.dict(cs.LITELLM_MODEL_CONFIG, {"Perplexity Sonar": {"input_cost_per_query": 0.005}}):
            cost = cs.CreditService._compute_credit_cost(usage_response)
        # 0 + 0.005 USD * 1.25 * 0.9 ≈ 0.005625
        assert cost == pytest.approx(0.005625)


# ---------------------------------------------------------------------------
# record_completion — the central decision point
# ---------------------------------------------------------------------------


class TestRecordCompletion:
    """
    Behavior matrix — see the file docstring. The Completion row is ALWAYS
    inserted; the difference is whether the cost gets subtracted from the
    company balance.
    """

    @pytest.mark.anyio
    async def test_pay_as_you_go_subtracts_and_records(self, user, usage_response):
        # Plan not in (free, premium, unlimited) → pay-as-you-go
        await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
            agent_or_task_prompt=False,
            subscription={"plan": "flex"},
        )

        _Companies.subtract_credit_balance.assert_called_once()
        _Completions.insert_new_completion.assert_called_once()
        # Completion record gets the computed cost — not zero
        args, _ = _Completions.insert_new_completion.call_args
        recorded_cost = args[2]
        assert recorded_cost > 0

    @pytest.mark.anyio
    @pytest.mark.parametrize("plan", ["free", "premium", "unlimited"])
    async def test_flat_rate_plan_tracks_cost_but_no_subtract(self, user, usage_response, plan):
        await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
            agent_or_task_prompt=False,
            subscription={"plan": plan},
        )

        _Companies.subtract_credit_balance.assert_not_called()
        _Completions.insert_new_completion.assert_called_once()
        args, _ = _Completions.insert_new_completion.call_args
        recorded_cost = args[2]
        # Flat-rate users have real cost recorded for internal analytics
        assert recorded_cost > 0

    @pytest.mark.anyio
    @pytest.mark.parametrize("plan", ["free", "premium", "unlimited", "flex", None])
    async def test_agent_prompt_never_subtracts_but_always_records(self, user, usage_response, plan):
        subscription = {"plan": plan} if plan else None
        await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
            agent_or_task_prompt=True,
            subscription=subscription,
        )

        _Companies.subtract_credit_balance.assert_not_called()
        _Completions.insert_new_completion.assert_called_once()
        args, _ = _Completions.insert_new_completion.call_args
        recorded_cost = args[2]
        from_agent = args[4]
        assert recorded_cost > 0
        assert from_agent is True

    @pytest.mark.anyio
    async def test_api_key_path_with_no_subscription_subtracts(self, user, usage_response):
        # main.py:668 calls record_completion(user, response, model) — defaults only.
        # subscription=None → must subtract (API-key callers pay per token).
        await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
        )

        _Companies.subtract_credit_balance.assert_called_once()
        _Completions.insert_new_completion.assert_called_once()

    @pytest.mark.anyio
    async def test_non_agent_call_records_from_agent_false(self, user, usage_response):
        await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
            agent_or_task_prompt=False,
            subscription={"plan": "free"},
        )
        args, _ = _Completions.insert_new_completion.call_args
        from_agent = args[4]
        assert from_agent is False

    @pytest.mark.anyio
    async def test_returns_computed_cost(self, user, usage_response):
        _litellm.completion_cost.return_value = 1.0
        cost = await cs.credit_service.record_completion(
            user, usage_response, "GPT-4o",
            agent_or_task_prompt=True,
            subscription={"plan": "flex"},
        )
        # 1 USD * 1.25 * 0.9 = 1.125 EUR
        assert cost == pytest.approx(1.125)


# ---------------------------------------------------------------------------
# subtract_credit_cost_by_user_and_response — thin wrapper
# ---------------------------------------------------------------------------


class TestSubtractCreditCost:
    @pytest.mark.anyio
    async def test_computes_then_subtracts(self, user, usage_response):
        cs.get_subscription.return_value = {"plan": "team_monthly"}
        _litellm.completion_cost.return_value = 2.0
        result = await cs.CreditService.subtract_credit_cost_by_user_and_response(user, usage_response)
        # 2 USD * 1.25 * 0.9 = 2.25 EUR
        assert result == pytest.approx(2.25)
        _Companies.subtract_credit_balance.assert_called_once()
        # Verify the amount actually subtracted matches
        subtracted_amount = _Companies.subtract_credit_balance.call_args[0][1]
        assert subtracted_amount == pytest.approx(2.25)

class TestPublicApiAccessGate:
    @pytest.mark.anyio
    @pytest.mark.parametrize("plan", ["free", "premium"])
    async def test_rejects_free_and_premium(self, user, plan):
        # Public /api/openai endpoints must reject flat-rate, scope-limited plans
        # because usage there is unmetered and would let customers bypass billing.
        from fastapi import HTTPException
        cs.get_subscription.return_value = {"plan": plan}
        with pytest.raises(HTTPException) as exc_info:
            await cs.CreditService.check_public_api_access(user)
        assert exc_info.value.status_code == 402

    @pytest.mark.anyio
    async def test_allows_unlimited_and_returns_subscription(self, user):
        # Kickstart customers (plan="unlimited") have full access by contract,
        # including the public API. The gate must let them through AND return
        # the subscription dict so callers can branch on the plan (to skip the
        # credit-subtract call for flat-rate plans).
        subscription = {"plan": "unlimited"}
        cs.get_subscription.return_value = subscription
        result = await cs.CreditService.check_public_api_access(user)
        assert result == subscription

    @pytest.mark.anyio
    async def test_credit_based_plan_returns_subscription(self, user):
        subscription = {"plan": "team_monthly", "status": "active", "seats": 5, "seats_taken": 1}
        cs.get_subscription.return_value = subscription
        result = await cs.CreditService.check_public_api_access(user)
        assert result == subscription
