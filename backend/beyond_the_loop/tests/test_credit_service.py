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


# litellm.types.utils stub — STT path does `from litellm.types.utils import
# TranscriptionResponse` at call time. The real class is a Pydantic model with
# a strict schema; a plain object that accepts attribute writes is enough for
# us since completion_cost is mocked.
class _StubTranscriptionResponse:
    def __init__(self, text=""):
        self.text = text
        self.duration = 0

_stub_module("litellm.types", utils=MagicMock(TranscriptionResponse=_StubTranscriptionResponse))
_stub_module("litellm.types.utils", TranscriptionResponse=_StubTranscriptionResponse)

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

# beyond_the_loop.services.email_service stub — instance-shaped so tests can
# assert on which method was called on the EmailService object created inside
# credit_service (EmailService() returns the same return_value each time).
_EmailServiceClass = MagicMock()
_stub_module("beyond_the_loop.services.email_service", EmailService=_EmailServiceClass)

# beyond_the_loop.config stub
_stub_module(
    "beyond_the_loop.config",
    LITELLM_MODEL_CONFIG={},
    LITELLM_MODEL_MAP={
        "GPT-4o": "azure/gpt-4o",
        # Aliases used by the STT/TTS subtract paths
        "STT": "azure/whisper",
        "TTS": "azure/tts-1",
    },
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
    _Companies.update_auto_recharge.reset_mock()
    _Companies.get_base_credit_balance.return_value = 1000.0
    _Companies.get_credit_balance.return_value = 1000.0
    _Companies.get_eighty_percent_credit_limit.return_value = 200.0
    _Companies.get_auto_recharge.return_value = False
    _EmailServiceClass.reset_mock()
    _Users.get_admin_users_by_company.reset_mock(return_value=True)
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


# ---------------------------------------------------------------------------
# subtract_credits_by_user_for_stt / _for_tts
#
# Voice paths were the missing piece in the Rudel recharge-loop investigation:
# they deducted credits but left no row in `completion`, so debugging the
# spend pattern required math-back from balance totals. These tests pin the
# new behavior — every successful subtract must insert a row, kinded so
# analytics queries can opt in or out.
# ---------------------------------------------------------------------------


class TestSubtractForSTT:
    @pytest.mark.anyio
    async def test_paid_plan_subtracts_and_inserts(self, user):
        _litellm.completion_cost.return_value = 0.10  # USD
        response = {"text": "hallo welt", "duration": 3.2}

        await cs.credit_service.record_stt_usage(user, response, {"plan": "team_monthly"})

        _Companies.subtract_credit_balance.assert_called_once()
        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        # Positional: user_id, model, credits_used, assistant, from_agent
        assert args[0] == user.id
        assert args[1] == "azure/whisper"  # LITELLM_MODEL_MAP["STT"]
        # 0.10 USD * 1.25 margin * 0.9 EUR/USD = 0.1125
        assert args[2] == pytest.approx(0.1125)
        assert args[3] is None       # assistant
        assert args[4] is False      # from_agent
        assert kwargs.get("kind") == "stt"

    @pytest.mark.anyio
    @pytest.mark.parametrize("plan", ["free", "premium", "unlimited"])
    async def test_flat_rate_inserts_row_but_does_not_subtract(self, user, plan):
        _litellm.completion_cost.return_value = 0.10
        response = {"text": "hallo welt", "duration": 3.2}

        await cs.credit_service.record_stt_usage(user, response, {"plan": plan})

        _Companies.subtract_credit_balance.assert_not_called()
        # Row still written so analytics can see voice activity
        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        assert kwargs.get("kind") == "stt"
        assert args[2] == pytest.approx(0.1125)

    @pytest.mark.anyio
    async def test_missing_subscription_falls_back_to_subtracting(self, user):
        # `subscription=None` (callers that haven't been migrated yet) should
        # treat it as a non-flat-rate plan to avoid silently giving away credits.
        _litellm.completion_cost.return_value = 0.10
        response = {"text": "x", "duration": 1.0}

        await cs.credit_service.record_stt_usage(user, response, None)

        _Companies.subtract_credit_balance.assert_called_once()
        _Completions.insert_new_completion.assert_called_once()

    @pytest.mark.anyio
    async def test_still_inserts_when_pricing_lookup_fails(self, user):
        # If litellm can't price the model we still want a paper trail.
        # The subtract path swallows the exception and uses 0; the row should
        # still be written for audit purposes.
        _litellm.completion_cost.side_effect = Exception("unknown model")
        response = {"text": "x", "duration": 1.0}

        await cs.credit_service.record_stt_usage(user, response, {"plan": "team_monthly"})

        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        assert args[2] == 0.0
        assert kwargs.get("kind") == "stt"


class TestSubtractForTTS:
    @pytest.mark.anyio
    async def test_paid_plan_subtracts_and_inserts(self, user):
        _litellm.completion_cost.return_value = 0.02  # USD

        await cs.credit_service.record_tts_usage(user, "Sag hallo.", {"plan": "team_monthly"})

        _Companies.subtract_credit_balance.assert_called_once()
        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        assert args[0] == user.id
        assert args[1] == "azure/tts-1"  # LITELLM_MODEL_MAP["TTS"]
        # 0.02 USD * 1.25 * 0.9 = 0.0225
        assert args[2] == pytest.approx(0.0225)
        assert args[3] is None
        assert args[4] is False
        assert kwargs.get("kind") == "tts"

    @pytest.mark.anyio
    @pytest.mark.parametrize("plan", ["free", "premium", "unlimited"])
    async def test_flat_rate_inserts_row_but_does_not_subtract(self, user, plan):
        _litellm.completion_cost.return_value = 0.02

        await cs.credit_service.record_tts_usage(user, "x", {"plan": plan})

        _Companies.subtract_credit_balance.assert_not_called()
        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        assert kwargs.get("kind") == "tts"
        assert args[2] == pytest.approx(0.0225)

    @pytest.mark.anyio
    async def test_still_inserts_when_pricing_lookup_fails(self, user):
        _litellm.completion_cost.side_effect = Exception("unknown model")

        await cs.credit_service.record_tts_usage(user, "x", {"plan": "team_monthly"})

        _Completions.insert_new_completion.assert_called_once()
        args, kwargs = _Completions.insert_new_completion.call_args
        assert args[2] == 0.0
        assert kwargs.get("kind") == "tts"


# ---------------------------------------------------------------------------
# Auto-recharge card-decline handling
#
# Regression coverage for the July 2026 Deutscher Apotheker Verlag incident:
# a company with auto_recharge=true and a declined card generated ~500
# stripe.Invoice.pay attempts in ~48h because every subsequent completion
# re-triggered the recharge with no persisted failure state. On a card
# decline (HTTP 400 out of recharge_flex_credits) we now disable auto_recharge
# and notify admins so the loop cannot spin up again on the next completion.
# ---------------------------------------------------------------------------


class TestAutoRechargeCardDecline:
    @pytest.fixture(autouse=True)
    def _low_balance_and_auto_recharge_on(self, monkeypatch):
        # Force the recharge branch: balance below 80% threshold, auto_recharge
        # on, one card on file, budget_mail_80 already sent (so we don't fan
        # out through the warning-mail path).
        _Companies.get_base_credit_balance.return_value = 0.0
        _Companies.get_credit_balance.return_value = 63.0
        _Companies.get_eighty_percent_credit_limit.return_value = 90.0
        _Companies.get_auto_recharge.return_value = True
        # NB: ``name`` is reserved on MagicMock (sets the mock's display name,
        # not a real attribute), so set company.name explicitly.
        company_mock = MagicMock(
            id="company-1",
            stripe_customer_id="cus_1",
            budget_mail_80_sent=True,
        )
        company_mock.name = "ACME"
        _Companies.get_company_by_id.return_value = company_mock
        # stripe.PaymentMethod.list returns a card
        pm_list = MagicMock()
        pm_list.data = [MagicMock(id="pm_1")]
        cs.stripe.PaymentMethod.list = MagicMock(return_value=pm_list)
        _Users.get_admin_users_by_company.return_value = [
            MagicMock(email="admin@acme.com", first_name="Ada"),
        ]
        # billing_page_link uses os.getenv("FRONTEND_BASE_URL") + suffix — set
        # it here so the string concat doesn't blow up in the decline branch.
        monkeypatch.setenv("FRONTEND_BASE_URL", "https://app.example.com")
        yield

    @pytest.mark.anyio
    async def test_card_decline_disables_auto_recharge_and_notifies_admins(self, user, usage_response):
        from fastapi import HTTPException

        # recharge_flex_credits raises a 400 on card decline (see payments.py).
        with patch.object(
            cs.CreditService, "recharge_flex_credits",
            side_effect=HTTPException(status_code=400, detail="Card declined: card was declined."),
        ):
            await cs.credit_service.record_completion(
                user, usage_response, "GPT-4o",
                agent_or_task_prompt=False,
                subscription={"plan": "enterprise_monthly"},
            )

        # auto_recharge flipped off so the next completion doesn't try again
        _Companies.update_auto_recharge.assert_called_once_with(user.company_id, False)
        # Admin notified about the disable
        _EmailServiceClass.return_value.send_auto_recharge_disabled_mail.assert_called_once()
        call_kwargs = _EmailServiceClass.return_value.send_auto_recharge_disabled_mail.call_args.kwargs
        assert call_kwargs["to_email"] == "admin@acme.com"
        assert call_kwargs["admin_name"] == "Ada"
        assert call_kwargs["company_name"] == "ACME"
        # Completion row is still written even though the recharge failed
        _Completions.insert_new_completion.assert_called_once()

    @pytest.mark.anyio
    async def test_non_400_recharge_error_does_not_disable(self, user, usage_response):
        # A 500 (Stripe API glitch, network, ...) is transient — don't punish
        # the customer by flipping auto_recharge off.
        from fastapi import HTTPException

        with patch.object(
            cs.CreditService, "recharge_flex_credits",
            side_effect=HTTPException(status_code=500, detail="Failed to recharge credits"),
        ):
            await cs.credit_service.record_completion(
                user, usage_response, "GPT-4o",
                agent_or_task_prompt=False,
                subscription={"plan": "enterprise_monthly"},
            )

        _Companies.update_auto_recharge.assert_not_called()
        _EmailServiceClass.return_value.send_auto_recharge_disabled_mail.assert_not_called()

    @pytest.mark.anyio
    async def test_successful_recharge_leaves_auto_recharge_untouched(self, user, usage_response):
        with patch.object(cs.CreditService, "recharge_flex_credits", new=AsyncMock(return_value={"ok": True})):
            await cs.credit_service.record_completion(
                user, usage_response, "GPT-4o",
                agent_or_task_prompt=False,
                subscription={"plan": "enterprise_monthly"},
            )

        _Companies.update_auto_recharge.assert_not_called()
        _EmailServiceClass.return_value.send_auto_recharge_disabled_mail.assert_not_called()
