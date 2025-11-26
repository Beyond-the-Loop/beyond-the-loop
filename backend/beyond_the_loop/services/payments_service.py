from fastapi import HTTPException

import stripe
import os
import time

from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users


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

        self.stripe_price_id_business_monthly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_MONTHLY',
                                                          "price_1Rgl6vBBwyxb4MZjHFAg6034")
        self.stripe_price_id_business_yearly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_YEARLY',
                                                         "price_1RglAcBBwyxb4MZjRYcvp9dr")
        self.stripe_price_id_business_two_yearly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_TWO_YEARLY',
                                                             "price_1SFK4QBBwyxb4MZjdHFP4AJh")

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
            "team_quarterly": {
                "price": 44700,  # 447,00€ in cents,
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_quarterly,
                "seats": 25
            },
            "team_yearly": {
                "price": 161000,  # 1.610,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_yearly,
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
            }
        }

    def get_plan_details_from_subscription(self, subscription):
        """
        Extract plan details and product image from a Stripe subscription.

        Args:
            subscription: Stripe subscription object

        Returns:
            tuple: (plan_id, plan_details, image_url)
        """
        price_id = subscription.plan.id

        plan_id, plan = next(
            ((plan, details) for plan, details in self.SUBSCRIPTION_PLANS.items() if
             details.get("stripe_price_id") == price_id),
            (None, {}))

        # Get the image url of the product
        product = stripe.Product.retrieve(subscription.plan.product)
        image_url = product.images[0] if product.images and len(product.images) > 0 else None

        return plan_id, plan, image_url

    def get_subscription(self, company_id):
        """Get the current subscription details for the company"""
        try:
            company = Companies.get_company_by_id(company_id)

            if company.subscription_not_required:
                return {
                    "plan": "unlimited",
                    "flex_credits_remaining": company.flex_credit_balance,
                    "seats": "unlimited",
                    "auto_recharge": company.auto_recharge
                }

            # Get subscription from Stripe
            active_subscriptions = stripe.Subscription.list(
                customer=company.stripe_customer_id,
                status='active',
                limit=1
            )

            # Check for trial subscriptions
            trial_subscriptions = stripe.Subscription.list(
                customer=company.stripe_customer_id,
                status='trialing',
                limit=1
            )

            # If there's an active trial subscription and no active subscription
            if trial_subscriptions.data and len(trial_subscriptions.data) > 0 and not active_subscriptions.data:
                trial_subscription = trial_subscriptions.data[0]

                # Calculate days remaining in trial
                current_time = int(time.time())
                trial_end = trial_subscription.trial_end
                days_remaining = max(0, int((trial_end - current_time) / (24 * 60 * 60)))

                plan_id, plan, image_url = self.get_plan_details_from_subscription(trial_subscription)

                return {
                    'credits_remaining': company.credit_balance,
                    'flex_credits_remaining': company.flex_credit_balance,
                    'plan': plan_id,
                    'is_trial': True,
                    "seats": plan.get("seats", 0),
                    "seats_taken": Users.count_users_by_company_id(company_id),
                    'trial_end': trial_end,
                    'days_remaining': days_remaining,
                    'image_url': image_url
                }

            if not active_subscriptions.data:
                # get last active subscription from stripe
                last_subscription = stripe.Subscription.list(
                    customer=company.stripe_customer_id,
                    status='all',
                    limit=1
                ).data[0]

                plan_id, plan, image_url = self.get_plan_details_from_subscription(last_subscription)

                return {
                    'credits_remaining': company.credit_balance,
                    'flex_credits_remaining': company.flex_credit_balance,
                    'plan': plan_id,
                    "status": last_subscription.status,
                    "seats": plan.get("seats", 0),
                    "canceled_at": last_subscription.canceled_at if hasattr(last_subscription, 'canceled_at') else None,
                    "seats_taken": Users.count_users_by_company_id(company_id),
                    "image_url": image_url
                }

            subscription = active_subscriptions.data[0]

            plan_id, plan, image_url = self.get_plan_details_from_subscription(subscription)

            return {
                "plan": plan_id,
                "status": subscription.status,
                "start_date": subscription.current_period_start,
                "end_date": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at if hasattr(subscription, 'canceled_at') else None,
                "will_renew": not subscription.cancel_at_period_end and subscription.status == 'active',
                "next_billing_date": subscription.current_period_end if not subscription.cancel_at_period_end and subscription.status == 'active' else None,
                "flex_credits_remaining": company.flex_credit_balance,
                "credits_remaining": company.credit_balance,
                "seats": plan.get("seats", 0),
                "seats_taken": Users.count_users_by_company_id(company_id),
                "auto_recharge": company.auto_recharge,
                "image_url": image_url
            }

        except Exception as e:
            print(f"Error getting subscription: {e}")
            raise HTTPException(status_code=500, detail=str(e))

payments_service = PaymentsService()