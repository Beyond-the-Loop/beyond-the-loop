import logging
import os
import stripe
import litellm
from typing import Optional
from fastapi import HTTPException
from nltk.chat.zen import responses

from beyond_the_loop.models.users import UserModel
from open_webui.env import SRC_LOG_LEVELS
from beyond_the_loop.models.users import Users
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.completions import Completions
from beyond_the_loop.services.email_service import EmailService
from beyond_the_loop.config import LITELLM_MODEL_CONFIG, LITELLM_MODEL_MAP

from beyond_the_loop.routers.payments import get_subscription

PROFIT_MARGIN_FACTOR = 1.25
EUR_PER_DOLLAR = 0.9

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


class CreditService:
    def __init__(self):
        """Initialize the CreditService."""
        pass

    async def _subtract_credits_by_user_and_credits(self, user, credit_cost: float):
        """
        Subtract credits from a company's balance and handle low balance scenarios.
        
        Args:
            user: The user making the request
            credit_cost: The number of credits to subtract
            
        Returns:
            Total credit cost
        """

        # Get current balance
        current_base_credit_balance = Companies.get_base_credit_balance(user.company_id)
        current_credit_balance = self.get_credit_balance(user.company_id)

        # Get the dynamic credit limit based on subscription
        eighty_percent_credit_limit = Companies.get_eighty_percent_credit_limit(user.company_id)

        # Check 80% threshold
        if current_base_credit_balance - credit_cost < eighty_percent_credit_limit:
            should_send_budget_email_80 = True  # Default to sending email

            company = Companies.get_company_by_id(user.company_id)

            # Recharge if base_credits + flex_credits - credit_cost < 80% of credit limit
            if Companies.get_auto_recharge(user.company_id) and current_credit_balance - credit_cost < eighty_percent_credit_limit:
                try:
                    # Check if the company has a stripe customer ID and payment method before recharging
                    if not company.stripe_customer_id:
                        log.warning(f"Auto-recharge failed: No stripe customer ID for company {user.company_id}")
                        # Don't attempt to recharge if there's no stripe customer ID
                    else:
                        # Check if the customer has any payment methods
                        try:
                            payment_methods = stripe.PaymentMethod.list(
                                customer=company.stripe_customer_id,
                                type="card"
                            )

                            if not payment_methods or len(payment_methods.data) == 0:
                                log.warning(
                                    f"Auto-recharge failed: No payment methods found for company {user.company_id}")
                                # Don't attempt to recharge if there are no payment methods
                            else:
                                # Trigger auto-recharge using the charge_customer endpoint
                                await self.recharge_flex_credits(user)
                                # Note: The webhook will handle adding the credits when payment succeeds
                                should_send_budget_email_80 = False  # Don't send email if auto-recharge succeeded
                        except Exception as e:
                            log.error(f"Error checking payment methods: {str(e)}")
                except HTTPException as e:
                    log.error(f"Auto-recharge failed: {str(e)}")
                except Exception as e:
                    log.error(f"Unexpected error during auto-recharge: {str(e)}")

            if should_send_budget_email_80 and not company.budget_mail_80_sent:
                admins = Users.get_admin_users_by_company(company.id)

                for admin in admins:
                    email_service = EmailService()
                    email_service.send_budget_mail_80(
                        to_email=admin.email,
                        admin_name=admin.first_name,
                        company_name=company.name,
                        billing_page_link=os.getenv("FRONTEND_BASE_URL") + "?modal=company-settings&tab=billing"
                    )

                Companies.update_company_by_id(company.id, {"budget_mail_80_sent": True})

        # Subtract credits from balance
        Companies.subtract_credit_balance(user.company_id, credit_cost)

        return credit_cost

    async def subtract_credits_by_user_for_stt(self, user, response):
        litellm_model = LITELLM_MODEL_MAP.get("STT", "")

        try:
            from litellm.types.utils import TranscriptionResponse
            duration_seconds = response.get("duration", 0)
            transcription_response = TranscriptionResponse(text=response.get("text", ""))
            transcription_response.duration = duration_seconds

            cost_usd = litellm.completion_cost(
                model=litellm_model,
                call_type="transcription",
                completion_response=transcription_response,
            )
        except Exception as e:
            log.warning(f"litellm.completion_cost failed for {litellm_model}: {e}")
            cost_usd = 0

        cost = cost_usd * PROFIT_MARGIN_FACTOR * EUR_PER_DOLLAR
        await self._subtract_credits_by_user_and_credits(user, cost)

    async def subtract_credits_by_user_for_tts(self, user, input_text: str):
        litellm_model = LITELLM_MODEL_MAP.get("TTS", "")

        try:
            cost_usd = litellm.completion_cost(
                model=litellm_model,
                call_type="speech",
                prompt=input_text,
            )
        except Exception as e:
            log.warning(f"litellm.completion_cost failed for {litellm_model}: {e}")
            cost_usd = 0

        cost = cost_usd * PROFIT_MARGIN_FACTOR * EUR_PER_DOLLAR
        await self._subtract_credits_by_user_and_credits(user, cost)

    async def subtract_credits_by_user_for_web_search(self, user):
        await self._subtract_credits_by_user_and_credits(user, 0.05 * PROFIT_MARGIN_FACTOR)

    async def subtract_credits_by_user_for_code_interpreter(self, user):
        await self._subtract_credits_by_user_and_credits(user, 0.05 * PROFIT_MARGIN_FACTOR)

    @staticmethod
    async def recharge_flex_credits(user):
        from beyond_the_loop.routers.payments import recharge_flex_credits
        return await recharge_flex_credits(user)

    @staticmethod
    def get_credit_balance(company_id: str) -> Optional[int]:
        """
        Get the current credit balance for a company.
        
        Args:
            company_id: The ID of the company
            
        Returns:
            int: The current credit balance, or None if the company doesn't exist
        """
        return Companies.get_credit_balance(company_id)

    @staticmethod
    async def check_for_subscription_and_sufficient_balance_and_seats(user):
        # First check if the user has an active subscription in Stripe
        company = Companies.get_company_by_id(user.company_id)

        # Get the active subscription to check seat limits
        subscription_details = get_subscription(user)

        if not company.subscription_not_required and not subscription_details.get("plan") == "free" and not subscription_details.get("plan") == "premium":
            # Get current seat count and limit
            seats_limit = subscription_details.get("seats", 0)
            seats_taken = subscription_details.get("seats_taken", 0)

            too_many_seats_taken = seats_taken > seats_limit

            if too_many_seats_taken:
                raise HTTPException(
                    status_code=402,  # 402 Payment Required
                    detail="You have reached the maximum number of seats in your subscription. Please upgrade your plan or remove some users.",
                )

            if not company or not company.stripe_customer_id or not (subscription_details.get("status") == "active" or subscription_details.get("is_trial")):
                raise HTTPException(
                    status_code=402,  # 402 Payment Required
                    detail="No active subscription found. Please subscribe to a plan.",
                )

            # Proceed with credit balance check
            current_balance = company.credit_balance + (company.flex_credit_balance or 0) if company else None

            # Check if company has sufficient credits
            if current_balance == 0:
                if not company.budget_mail_100_sent:
                    email_service = EmailService()
                    email_service.send_budget_mail_100(
                        to_email=user.email,
                        admin_name=user.first_name,
                        company_name=company.name,
                        billing_page_link=os.getenv("FRONTEND_BASE_URL") + "?modal=company-settings&tab=billing"
                    )

                    Companies.update_company_by_id(user.company_id, {"budget_mail_100_sent": True})

                raise HTTPException(
                    status_code=402,  # 402 Payment Required
                    detail=f"Insufficient credits. No credits left.",
                )

    @staticmethod
    async def subtract_credit_cost_by_user_and_response(user: UserModel, response):
        model_name = response.get("model")

        litellm_model = LITELLM_MODEL_MAP.get(model_name, "")
        pricing_model = litellm_model.replace("azure/responses/", "azure/")

        if pricing_model != "azure/gpt-5.1-chat" and pricing_model != "azure/gpt-5.3-chat":
            pricing_model = pricing_model.replace("azure/", "azure_ai/")

        if pricing_model == "azure_ai/deepseek-r1-0528":
            pricing_model = "lambda_ai/deepseek-r1-0528"

        if pricing_model == "perplexity/sonar":
            pricing_model = "perplexity/sonar-pro"

        try:
            token_cost_usd = litellm.completion_cost(
                model=pricing_model,
                completion_response=response,
            )
        except Exception as e:
            log.warning(f"litellm.completion_cost failed for {pricing_model}: {e}")
            token_cost_usd = 0

        if token_cost_usd == 0:
            log.warning(f"Unknown or zero pricing for model {model_name} ({litellm_model})")

        # input_cost_per_query is a custom field not in LiteLLM's pricing table
        search_query_cost = 0
        if "Perplexity" in model_name:
            pricing = litellm.model_cost.get(litellm_model) or LITELLM_MODEL_CONFIG.get(model_name, {})
            search_query_cost = pricing.get("input_cost_per_query", 0)

        total_costs = (token_cost_usd + search_query_cost) * PROFIT_MARGIN_FACTOR * EUR_PER_DOLLAR

        input_tokens = response.get('usage', {}).get('prompt_tokens', 0)
        output_tokens = response.get('usage', {}).get('completion_tokens', 0)
        completion_tokens_details = response.get('usage', {}).get('completion_tokens_details') or {}
        reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)

        return await credit_service._subtract_credits_by_user_and_credits(user, total_costs)

credit_service = CreditService()