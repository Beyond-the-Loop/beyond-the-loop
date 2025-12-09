from time import strftime

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException

import stripe
import os
import time
from datetime import date, datetime

from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users
from beyond_the_loop.services.crm_service import crm_service


def _set_new_credit_recharge_check_date(company):
    try:
        # Add one month
        next_check_date = date.today() + relativedelta(months=1)
        # Update the field as timestamp
        next_credit_charge_check = datetime.combine(next_check_date, datetime.min.time()).timestamp()

        Companies.update_company_by_id(company.id, {"next_credit_charge_check": next_credit_charge_check})
    except Exception as e:
        print(f"Failed to update next credit charge check date for company {company.id}: {e}")


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

        self.stripe_price_id_enterprise_monthly = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_MONTHLY', 'price_1RglhLBBwyxb4MZjTgmXgtSV')

        self.stripe_price_id_enterprise_yearly = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE_YEARLY', 'price_1RgliHBBwyxb4MZjb1rAH3tS')

        # Constants
        self.FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS = 2000  # Amount in cents (20 euro)

        # Subscription Plans
        self.SUBSCRIPTION_PLANS = {
            "starter_monthly": {
                "price": 2500,  # 25€ in cents
                "credits_per_month": 5,
                "stripe_price_id": self.stripe_price_id_starter_monthly,
                "seats": 5,
                "months": 1
            },
            "starter_yearly": {
                "price": 27000,  # 270,00€ in cents
                "credits_per_month": 5,
                "stripe_price_id": self.stripe_price_id_starter_yearly,
                "seats": 5,
                "months": 12
            },
            "team_monthly": {
                "price": 14900,  # 149,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_monthly,
                "seats": 25,
                "months": 1
            },
            "team_yearly": {
                "price": 161000,  # 1.610,00€ in cents
                "credits_per_month": 50,
                "stripe_price_id": self.stripe_price_id_team_yearly,
                "seats": 25,
                "months": 12
            },
            "business_monthly": {
                "price": 44900,  # 449€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_monthly,
                "seats": 100,
                "months": 1
            },
            "business_yearly": {
                "price": 484900,  # 4.849,00€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_yearly,
                "seats": 100,
                "months": 12
            },
            "business_two_yearly": {
                "price": 969800,  # 9.698,00€ in cents
                "credits_per_month": 150,
                "stripe_price_id": self.stripe_price_id_business_two_yearly,
                "seats": 100,
                "months": 24
            },
            "enterprise_monthly": {
                "price": 124900, # 1.249,00€ in cents,
                "credits_per_month": 450,
                "stripe_price_id": self.stripe_price_id_enterprise_monthly,
                "seats": 1000,
                "months": 1
            },
            "enterprise_yearly": {
                "price": 1348900,  # 13.489,00€ in cents,
                "credits_per_month": 450,
                "stripe_price_id": self.stripe_price_id_enterprise_yearly,
                "seats": 1000,
                "months": 12
            }
        }

    def update_company_credits_from_subscription(self, event_data, action_description, is_invoice=False):
        """
        Helper function to update company credits based on subscription data.

        Args:
            event_data: The subscription data from the Stripe webhook event
            action_description: Description of the action being performed (for logging)
            is_invoice: Whether the event data is from an invoice event (vs subscription event)

        Returns:
            tuple: (company, credits_per_month, plan_id) or (None, None, None) if any step fails
        """
        try:
            billing_reason = event_data.get('billing_reason')

            # If the billing reason is not subscription_create, ignore the event
            if billing_reason == 'subscription_create' or billing_reason == 'subscription_update':
                return None, None, None

            # Extract subscription details
            if is_invoice:
                subscription_id = event_data.get('subscription')
                # For invoice events, we need to check the billing reason
            else:
                subscription_id = event_data.get('id')

            stripe_customer_id = event_data.get('customer')

            if not subscription_id or not stripe_customer_id:
                print("Missing subscription_id or customer_id in event data")
                return None, None, None

            # Get the company associated with this Stripe customer
            company = Companies.get_company_by_stripe_customer_id(stripe_customer_id)

            if not company:
                return None, None, None

            # For invoice events, we need to fetch the subscription to get items
            if is_invoice:
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    items = subscription.get('items', {}).get('data', [])
                except Exception as e:
                    print(f"Error retrieving subscription {subscription_id}: {e}")
                    return None, None, None
            else:
                # Get the price ID from the subscription
                items = event_data.get('items', {}).get('data', [])

            if not items:
                print(f"No items found in subscription {subscription_id}")
                return None, None, None

            price_id = items[0].get('price', {}).get('id')

            if not price_id:
                print(f"No price ID found in subscription {subscription_id}")
                return None, None, None

            # Find the plan associated with this price ID
            plan_id = next((plan for plan, details in payments_service.SUBSCRIPTION_PLANS.items()
                            if details.get("stripe_price_id") == price_id), None)

            if not plan_id or plan_id not in payments_service.SUBSCRIPTION_PLANS:
                print(f"No plan found for price ID: {price_id}")
                return None, None, None

            # Check for custom credit amount in subscription metadata
            subscription_metadata = {}
            if is_invoice:
                # For invoice events, get metadata from the subscription
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    subscription_metadata = subscription.get('metadata', {})
                except Exception as e:
                    print(f"Error retrieving subscription metadata for {subscription_id}: {e}")
                    subscription_metadata = {}
            else:
                # For subscription events, get metadata directly from event data
                subscription_metadata = event_data.get('metadata', {})

            # Check if custom_credit_amount is specified in metadata
            custom_credit_amount = subscription_metadata.get('custom_credit_amount')

            if custom_credit_amount:
                try:
                    credits_per_month = int(custom_credit_amount)
                    print(f"Using custom credit amount from metadata: {credits_per_month}")
                except (ValueError, TypeError):
                    print(
                        f"Invalid custom_credit_amount in metadata: {custom_credit_amount}, falling back to plan default")
                    credits_per_month = payments_service.SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)
            else:
                # Get the credits per month for this plan
                credits_per_month = payments_service.SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)

            # Add the credits to the company's balance
            if credits_per_month > 0:
                # Update the company's credit balance
                Companies.update_company_by_id(company.id, {
                    "credit_balance": credits_per_month,
                    "budget_mail_80_sent": False,
                    "budget_mail_100_sent": False
                })

                _set_new_credit_recharge_check_date(company)

                credit_source = "custom metadata" if custom_credit_amount else "plan default"

                print(f"{action_description.capitalize()} {credits_per_month} credits to company {company.id} for subscription {subscription_id} (source: {credit_source})")

            try:
                crm_service.update_company_plan(company_name=company.name, plan=plan_id.replace("_", " ").title())
                crm_service.update_company_last_subscription_renewal_date(company_name=company.name,
                                                                          renewal_date=strftime('%Y-%m-%d'))
            except Exception as e:
                print(f"Failed to update CRM for company {company.name}: {e}")

            return company, credits_per_month, plan_id

        except Exception as e:
            print(f"Error {action_description} subscription event: {e}")
            return None, None, None

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
                try:
                    # get last active subscription from stripe
                    last_subscription = stripe.Subscription.list(
                        customer=company.stripe_customer_id,
                        status='all',
                        limit=1
                    ).data[0]
                except IndexError:
                    # No subscription ever existed for customer
                    return {
                        'credits_remaining': company.credit_balance,
                        'flex_credits_remaining': company.flex_credit_balance,
                        "seats": 0,
                        "seats_taken": Users.count_users_by_company_id(company_id),
                    }

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
                "image_url": image_url,
                "custom_credit_amount": int(subscription.metadata.get("custom_credit_amount")) if subscription.metadata.get("custom_credit_amount") is not None else None,
                "next_credit_recharge": company.next_credit_charge_check
            }

        except Exception as e:
            print(f"Error getting subscription: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def run_credit_recharge_checks(self):
        try:
            due_companies = Companies.get_companies_due_for_credit_recharge_check()

            # Update their next_credit_charge_check to the same day next month
            for company in due_companies:
                subscription = payments_service.get_subscription(company.id)

                if subscription.get("is_trial", False) or subscription.get("status", False) == "active":
                    print("SET NEXT CREDIT RECHARGE CHECK FOR COMPANY:", company.id)

                    Companies.update_company_by_id(company.id, {
                        "credit_balance": subscription.get("custom_credit_amount", False) or self.SUBSCRIPTION_PLANS.get(subscription.get("plan", ""), {}).get("credits_per_month", 0),
                        "budget_mail_80_sent": False,
                        "budget_mail_100_sent": False
                    })

                    _set_new_credit_recharge_check_date(company)
                else:
                    print("SET NEXT CREDIT RECHARGE CHECK TO NULL FOR COMPANY:", company.id)
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

payments_service = PaymentsService()