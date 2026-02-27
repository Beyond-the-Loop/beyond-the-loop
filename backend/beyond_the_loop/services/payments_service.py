import logging
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException

import stripe
import os
import time
from datetime import datetime

log = logging.getLogger(__name__)

from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users
from beyond_the_loop.services.crm_service import crm_service
import re

from beyond_the_loop.socket.main import STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE, STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE, STRIPE_PRODUCT_CACHE

def _set_new_credit_recharge_check_date(company):
    try:
        # Convert the existing timestamp to datetime
        if company.next_credit_charge_check:
            last_check_dt = datetime.fromtimestamp(company.next_credit_charge_check)
        else:
            last_check_dt = datetime.now()

        # Add one month
        next_check_dt = last_check_dt + relativedelta(months=1)

        # Convert back to timestamp
        next_credit_charge_check = next_check_dt.timestamp()

        Companies.update_company_by_id(
            company.id,
            {"next_credit_charge_check": next_credit_charge_check}
        )

    except Exception as e:
        log.error(
            f"Failed to update next credit charge check date for company "
            f"{company.id}: {e}"
        )


class PaymentsService:

    def __init__(self):
        stripe.api_key = os.environ.get('STRIPE_API_KEY')
        self.webhook_secret = os.environ.get('WEBHOOK_SECRET')
        self.stripe_pricing_table_id = os.environ.get('STRIPE_PRICING_TABLE_ID')
        self.stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')

        self.stripe_price_id_starter_monthly = os.environ.get('STRIPE_PRICE_ID_STARTER_MONTHLY',
                                                         "price_1RNq8xBBwyxb4MZjy1k0SneL")
        self.stripe_price_id_starter_yearly = os.environ.get('STRIPE_PRICE_ID_STARTER_YEARLY',
                                                        "price_1RNq8xBBwyxb4MZjfz68raOh")

        self.stripe_price_id_team_monthly = os.environ.get('STRIPE_PRICE_ID_TEAM_MONTHLY', "price_1RNqAcBBwyxb4MZjAGivhdo7")
        self.stripe_price_id_team_quarterly = os.environ.get('STRIPE_PRICE_ID_TEAM_QUARTERLY',
                                                        "price_1SSM5YBBwyxb4MZj6pj9hNIH")
        self.stripe_price_id_team_yearly = os.environ.get('STRIPE_PRICE_ID_TEAM_YEARLY', "price_1RNqAcBBwyxb4MZjNdS4XrNc")

        self.stripe_price_id_team_two_yearly = os.environ.get('STRIPE_PRICE_ID_TEAM_TWO_YEARLY', 'price_1SecChBBwyxb4MZjwC1dBei8')

        self.stripe_price_id_business_monthly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_MONTHLY',
                                                          "price_1Rgl6vBBwyxb4MZjHFAg6034")
        self.stripe_price_id_business_yearly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_YEARLY',
                                                         "price_1RglAcBBwyxb4MZjRYcvp9dr")
        self.stripe_price_id_business_two_yearly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_TWO_YEARLY',
                                                             "price_1SFK4QBBwyxb4MZjdHFP4AJh")

        self.stripe_price_id_enterprise_monthly = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_MONTHLY', 'price_1RglhLBBwyxb4MZjTgmXgtSV')

        self.stripe_price_id_enterprise_yearly = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_YEARLY', 'price_1RgliHBBwyxb4MZjb1rAH3tS')

        self.stripe_price_id_user_seat = os.environ.get('STRIPE_PRICE_ID_USER_SEAT', 'price_1Sq9KwBBwyxb4MZj8okVXYiQ')

        # Constants
        self.FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS = 2000  # Amount in cents (20 euro)

        # Subscription Plans
        self.SUBSCRIPTION_PLANS = {
            "starter_monthly": {
                "price": 2500,  # 25€ in cents
                "credits_per_month": 5,
                "stripe_price_id": self.stripe_price_id_starter_monthly,
                "seats": 5
            },
            "starter_yearly": {
                "price": 27000,  # 270,00€ in cents
                "credits_per_month": 5,
                "stripe_price_id": self.stripe_price_id_starter_yearly,
                "seats": 5
            },
            "team_monthly": {
                "price": 14900,  # 149,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_monthly,
                "seats": 25
            },
            "team_yearly": {
                "price": 161000,  # 1.610,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_yearly,
                "seats": 25
            },
            "team_two_yearly": {
                "price": 357600,  # 3576,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_two_yearly,
                "seats": 25
            },
            "business_monthly": {
                "price": 44900,  # 449€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_monthly,
                "seats": 100
            },
            "business_yearly": {
                "price": 484900,  # 4.849,00€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_yearly,
                "seats": 100
            },
            "business_two_yearly": {
                "price": 969800,  # 9.698,00€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_two_yearly,
                "seats": 100
            },
            "enterprise_monthly": {
                "price": 124900, # 1.249,00€ in cents
                "credits_per_month": 450,
                "stripe_price_id": self.stripe_price_id_enterprise_monthly,
                "seats": 1000
            },
            "enterprise_yearly": {
                "price": 1348900,  # 13.489,00€ in cents
                "credits_per_month": 450,
                "stripe_price_id": self.stripe_price_id_enterprise_yearly,
                "seats": 1000
            },
            "premium": {
                "stripe_price_id": self.stripe_price_id_user_seat
            }
        }

        self.PREMIUM_BILLING_PORTAL_ID = os.getenv('STRIPE_PREMIUM_BILLING_PORTAL_ID', "bpc_1SnKqsBBwyxb4MZj4SRs4N0b")

    def get_plan_details_from_subscription(self, subscription):
        """
        Extract plan details and product image from a Stripe subscription.

        Args:
            subscription: Stripe subscription object

        Returns:
            tuple: (plan_id, plan_details, image_url)
        """
        price_id = subscription.get("plan").get("id")

        plan_id, plan = next(
            ((plan, details) for plan, details in self.SUBSCRIPTION_PLANS.items() if
             details.get("stripe_price_id") == price_id),
            (None, {}))

        # Get the image url of the product
        if subscription.get("plan").get("product") in STRIPE_PRODUCT_CACHE:
            product = STRIPE_PRODUCT_CACHE[subscription.get("plan").get("product")]
        else:
            product = stripe.Product.retrieve(subscription.get("plan").get("product"))
            STRIPE_PRODUCT_CACHE[subscription.get("plan").get("product")] = product

        image_url = product.get("images")[0] if product.get("images") and len(product.get("images")) > 0 else None

        return plan_id, plan, image_url

    def get_subscription(self, company_id):
        """Get the current subscription details for the company"""
        try:
            company = Companies.get_company_by_id(company_id)

            if company.subscription_not_required:
                return {
                    "plan": "unlimited",
                    "seats": "unlimited"
                }

            cached_active_subscriptions = STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE.get(company_id)

            # Get subscription from Stripe
            active_subscriptions = cached_active_subscriptions if cached_active_subscriptions else stripe.Subscription.list(
                customer=company.stripe_customer_id,
                status='active',
                limit=1
            )

            if not cached_active_subscriptions:
                STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE[company_id] = active_subscriptions

            cached_trial_subscriptions = STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE.get(company_id)

            # Check for trial subscriptions
            trial_subscriptions = cached_trial_subscriptions if cached_trial_subscriptions else stripe.Subscription.list(
                customer=company.stripe_customer_id,
                status='trialing',
                limit=1
            )

            if not cached_trial_subscriptions:
                STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE[company_id] = trial_subscriptions

            # If there's an active trial subscription and no active subscription
            if trial_subscriptions.get("data") and len(trial_subscriptions.get("data")) > 0 and not active_subscriptions.get("data"):
                trial_subscription = trial_subscriptions.get("data")[0]

                # Calculate days remaining in trial
                current_time = int(time.time())
                trial_end = trial_subscription.get("trial_end")
                days_remaining = max(0, int((trial_end - current_time) / (24 * 60 * 60)))

                plan_id, plan, image_url = self.get_plan_details_from_subscription(trial_subscription)

                return {
                    'credits_remaining': company.credit_balance,
                    'flex_credits_remaining': company.flex_credit_balance,
                    'credits_per_month': plan.get("credits_per_month", 0),
                    'plan': plan_id,
                    'is_trial': True,
                    "seats": plan.get("seats", 0),
                    "seats_taken": Users.count_users_by_company_id(company_id),
                    'trial_end': trial_end,
                    'days_remaining': days_remaining,
                    'image_url': image_url,
                    "subscription_id": trial_subscription.get("id"),
                    "subscription_item_id": trial_subscription["items"]["data"][0]["id"]
                }

            # If no active subscription, return free plan
            if not active_subscriptions.get("data"):
                return {
                    "plan": "free",
                    "seats_taken": Users.count_users_by_company_id(company_id)
                }

            subscription = active_subscriptions.get("data")[0]

            plan_id, plan, image_url = self.get_plan_details_from_subscription(subscription)

            if plan_id == "premium":
                return {
                    "plan": plan_id,
                    "start_date": subscription.get("current_period_start"),
                    "end_date": subscription.get("current_period_end"),
                    "cancel_at_period_end": subscription.get("cancel_at_period_end"),
                    "canceled_at": subscription.get("canceled_at") if hasattr(subscription, 'canceled_at') else None,
                    "will_renew": not subscription.get("cancel_at_period_end") and subscription.get("status") == 'active',
                    "next_billing_date": subscription.get("current_period_end") if not subscription.get("cancel_at_period_end") and subscription.get("status") == 'active' else None,
                    "seats_taken": Users.count_users_by_company_id(company_id),
                    "image_url": image_url,
                    "subscription_id": subscription.get("id"),
                    "subscription_item_id": subscription["items"]["data"][0]["id"]
                }

            return {
                "plan": plan_id,
                "status": subscription.get("status"),
                "start_date": subscription.get("current_period_start"),
                "end_date": subscription.get("current_period_end"),
                "cancel_at_period_end": subscription.get("cancel_at_period_end"),
                "canceled_at": subscription.get("canceled_at") if hasattr(subscription, 'canceled_at') else None,
                "will_renew": not subscription.get("cancel_at_period_end") and subscription.get("status") == 'active',
                "next_billing_date": subscription.get("current_period_end") if not subscription.get("cancel_at_period_end") and subscription.get("status") == 'active' else None,
                "flex_credits_remaining": company.flex_credit_balance,
                "credits_remaining": company.credit_balance,
                "seats": plan.get("seats", 0),
                "seats_taken": Users.count_users_by_company_id(company_id),
                "auto_recharge": company.auto_recharge,
                "image_url": image_url,
                "credits_per_month": plan.get("credits_per_month", 0),
                "custom_credit_amount": int(subscription.get("metadata").get("custom_credit_amount")) if subscription.get("metadata").get("custom_credit_amount") is not None else None,
                "next_credit_recharge": company.next_credit_charge_check
            }

        except Exception as e:
            log.error(f"Error getting subscription: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def run_credit_recharge_checks(self):
        try:
            due_companies = Companies.get_companies_due_for_credit_recharge_check()

            # Update their next_credit_charge_check to the same day next month
            for company in due_companies:
                subscription = payments_service.get_subscription(company.id)

                if subscription.get("is_trial", False) or subscription.get("status", False) == "active":
                    Companies.update_company_by_id(company.id, {
                        "credit_balance": subscription.get("custom_credit_amount", False) or self.SUBSCRIPTION_PLANS.get(subscription.get("plan", ""), {}).get("credits_per_month", 0),
                        "budget_mail_80_sent": False,
                        "budget_mail_100_sent": False
                    })

                    _set_new_credit_recharge_check_date(company)
                else:
                    Companies.update_company_by_id(company.id, {
                        "next_credit_charge_check": None
                    })

            return {
                "success": True,
                "companies_processed": [c.id for c in due_companies]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # Legacy
    def handle_company_subscription_update(self, event_data):
        """
        Helper function to update company credits based on subscription data.

        Args:
            event_data: The subscription data from the Stripe webhook event

        Returns:
            tuple: (company, credits_per_month, plan_id) or (None, None, None) if any step fails
        """
        try:
            print("CREDITS [1]: handle_company_subscription_update entered", flush=True)

            canceled_at = event_data.get("canceled_at")
            print(f"CREDITS [2]: canceled_at={canceled_at}", flush=True)

            if canceled_at:
                print("CREDITS [3]: subscription is canceled — returning early", flush=True)
                return None, None, None

            subscription_id = event_data.get('id')
            stripe_customer_id = event_data.get('customer')
            print(f"CREDITS [4]: subscription_id={subscription_id}, stripe_customer_id={stripe_customer_id}", flush=True)

            if not subscription_id or not stripe_customer_id:
                print("CREDITS [ERR]: missing subscription_id or stripe_customer_id", flush=True)
                log.error("Missing subscription_id or customer_id in event data")
                return None, None, None

            company = Companies.get_company_by_stripe_customer_id(stripe_customer_id)
            print(f"CREDITS [5]: company={company}", flush=True)

            if not company:
                print(f"CREDITS [ERR]: no company for stripe_customer_id={stripe_customer_id}", flush=True)
                log.error(f"No company found for stripe_customer_id: {stripe_customer_id}")
                return None, None, None

            items = event_data.get('items', {}).get('data', [])
            print(f"CREDITS [6]: items count={len(items)}, items={items}", flush=True)

            if not items:
                print("CREDITS [ERR]: no items in subscription", flush=True)
                log.error(f"No items found in subscription {subscription_id}")
                return None, None, None

            price_id = items[0].get('price', {}).get('id')
            print(f"CREDITS [7]: price_id={price_id}", flush=True)

            if not price_id:
                print("CREDITS [ERR]: no price_id found", flush=True)
                log.error(f"No price ID found in subscription {subscription_id}")
                return None, None, None

            plan_id = next((plan for plan, details in payments_service.SUBSCRIPTION_PLANS.items()
                            if details.get("stripe_price_id") == price_id), None)
            print(f"CREDITS [8]: plan_id={plan_id}", flush=True)

            try:
                plan_name = re.sub(r"_", " ", plan_id)
                plan_name = re.sub(r"(\b\w)", lambda m: m.group(1).upper(), plan_name)
                crm_service.update_company_plan(company.name, plan_name)
            except Exception as e:
                print(f"CREDITS [WARN]: crm update failed: {e}", flush=True)
                log.error(f"Error updating Attio workspace plan for company {company.id}: {e}")

            if plan_id == "premium":
                print("CREDITS [9]: premium plan — no credits to add", flush=True)
                return None, None, None

            if not plan_id or plan_id not in payments_service.SUBSCRIPTION_PLANS:
                print(f"CREDITS [ERR]: plan not found for price_id={price_id}. Known: { {k: v.get('stripe_price_id') for k, v in payments_service.SUBSCRIPTION_PLANS.items()} }", flush=True)
                log.error(f"No plan found for price ID: {price_id}. Known price IDs: { {k: v.get('stripe_price_id') for k, v in payments_service.SUBSCRIPTION_PLANS.items()} }")
                return None, None, None

            subscription_metadata = event_data.get('metadata', {})
            custom_credit_amount = subscription_metadata.get('custom_credit_amount')
            print(f"CREDITS [10]: custom_credit_amount={custom_credit_amount}", flush=True)

            if custom_credit_amount:
                try:
                    credits_per_month = int(custom_credit_amount)
                except (ValueError, TypeError):
                    credits_per_month = payments_service.SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)
            else:
                credits_per_month = payments_service.SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)

            print(f"CREDITS [11]: credits_per_month={credits_per_month}", flush=True)

            if credits_per_month > 0:
                print(f"CREDITS [12]: updating company {company.id} with {credits_per_month} credits", flush=True)
                Companies.update_company_by_id(company.id, {
                    "credit_balance": credits_per_month,
                    "budget_mail_80_sent": False,
                    "budget_mail_100_sent": False
                })
                _set_new_credit_recharge_check_date(company)
                print(f"CREDITS [13]: company update done", flush=True)

            return company, credits_per_month, plan_id

        except Exception as e:
            print(f"CREDITS [ERR]: exception: {e}", flush=True)
            log.error(f"Error on adding credits from subscription event: {e}")
            return None, None, None


payments_service = PaymentsService()