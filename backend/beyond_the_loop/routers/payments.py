import stripe
from datetime import datetime
from pydantic import BaseModel
from fastapi import Depends, HTTPException, Request, Header, APIRouter
import os
from typing import Optional
import time
from time import strftime

from beyond_the_loop.models.users import Users
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.services.crm_service import crm_service
from open_webui.utils.auth import get_verified_user

router = APIRouter()

webhook_secret = os.environ.get('WEBHOOK_SECRET')
stripe.api_key = os.environ.get('STRIPE_API_KEY')
stripe_pricing_table_id = os.environ.get('STRIPE_PRICING_TABLE_ID')
stripe_publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY')

stripe_price_id_starter_monthly = os.environ.get('STRIPE_PRICE_ID_STARTER_MONTHLY', "price_1RNq8xBBwyxb4MZjy1k0SneL")
stripe_price_id_team_monthly = os.environ.get('STRIPE_PRICE_ID_TEAM_MONTHLY', "price_1RNqAcBBwyxb4MZjAGivhdo7")
stripe_price_id_business_monthly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_MONTHLY', "price_1Rgl6vBBwyxb4MZjHFAg6034")

stripe_price_id_starter_yearly = os.environ.get('STRIPE_PRICE_ID_STARTER_YEARLY', "price_1RNq8xBBwyxb4MZjfz68raOh")
stripe_price_id_team_yearly = os.environ.get('STRIPE_PRICE_ID_TEAM_YEARLY', "price_1RNqAcBBwyxb4MZjNdS4XrNc")
stripe_price_id_business_yearly = os.environ.get('STRIPE_PRICE_ID_BUSINESS_YEARLY', "price_1RglAcBBwyxb4MZjRYcvp9dr")

# Constants
FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS = 2000 # Amount in cents (20 euro)

# Subscription Plans
SUBSCRIPTION_PLANS = {
    "starter_monthly": {
        "price": 2500,  # 25€ in cents
        "credits_per_month": 5,
        "stripe_price_id": stripe_price_id_starter_monthly,
        "seats": 5
    },
    "starter_yearly": {
        "price": 27000,  # 270,00€ in cents
        "credits_per_month": 5,
        "stripe_price_id": stripe_price_id_starter_yearly,
        "seats": 5
    },
    "team_monthly": {
        "price": 14900,  # 149,00€ in cents
        "credits_per_month": 50,
        "stripe_price_id": stripe_price_id_team_monthly,
        "seats": 25
    },
    "team_yearly": {
        "price": 161000,  # 1.610,00€ in cents
        "credits_per_month": 50,
        "stripe_price_id": stripe_price_id_team_yearly,
        "seats": 25
    },
    "business_monthly": {
        "price": 44900,  # 449€ in cents
        "credits_per_month": 150,
        "stripe_price_id": stripe_price_id_business_monthly,
        "seats": 100
    },
    "business_yearly": {
        "price": 484900,  # 4.849,00€ in cents
        "credits_per_month": 150,
        "stripe_price_id": stripe_price_id_business_yearly,
        "seats": 100
    }
}

class SubscriptionPlanResponse(BaseModel):
    """Response model for subscription plans"""
    id: str
    price: int
    credits_per_month: int
    seats: int

class SubscriptionResponse(BaseModel):
    """Response model for company subscription details"""
    plan: str
    status: str
    start_date: Optional[int] = None
    end_date: Optional[int] = None
    credits_remaining: Optional[int] = None

class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription"""
    plan_id: str  # "basic", "pro", or "team"

class UpdateSubscriptionRequest(BaseModel):
    """Request model for updating a subscription"""
    plan_id: str  # "basic", "pro", or "team"


@router.get("/create-billing-portal-session/")
async def create_billing_portal_session(user=Depends(get_verified_user)):
    try:
        company = Companies.get_company_by_id(user.company_id)

        if not company.stripe_customer_id:
            raise HTTPException(status_code=404, detail="No customer found")

        # Create a billing portal session
        session = stripe.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            return_url=os.getenv('BACKEND_ADDRESS') + "?modal=company-settings&tab=billing",
        )

        return {"url": session.url}
    except Exception as e:
        print(f"Error creating billing portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customer-pricing-table-infos/")
async def customer_pricing_table_infos(user=Depends(get_verified_user)):
    try:
        company = Companies.get_company_by_id(user.company_id)

        if not company.stripe_customer_id:
            raise HTTPException(status_code=404, detail="No customer found")

        # Create a billing portal session
        session = stripe.CustomerSession.create(
            customer=company.stripe_customer_id,
            components={"pricing_table": {"enabled": True}},
        )

        return {"client_secret": session.client_secret, "pricing_table_id": stripe_pricing_table_id, "publishable_key": stripe_publishable_key}
    except Exception as e:
        print(f"Error creating billing portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get current subscription details
@router.get("/subscription/")
async def get_subscription(user=Depends(get_verified_user)):
    """Get the current subscription details for the company"""
    try:
        company = Companies.get_company_by_id(user.company_id)

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

        # If there's an active trial subscription
        if trial_subscriptions.data and len(trial_subscriptions.data) > 0 and not active_subscriptions.data:
            trial_subscription = trial_subscriptions.data[0]

            # Get the image url of the product
            product = stripe.Product.retrieve(trial_subscription.plan.product)
            image_url = product.images[0] if product.images else None
            
            # Calculate days remaining in trial
            current_time = int(time.time())
            trial_end = trial_subscription.trial_end
            days_remaining = max(0, int((trial_end - current_time) / (24 * 60 * 60)))
            
            return {
                'credits_remaining': company.credit_balance,
                'flex_credits_remaining': company.flex_credit_balance,
                'plan': 'free',
                'is_trial': True,
                "seats": 5,
                "seats_taken": Users.count_users_by_company_id(user.company_id),
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

            price_id = last_subscription.plan.id

            plan_id = next(
                (plan for plan, details in SUBSCRIPTION_PLANS.items() if details.get("stripe_price_id") == price_id),
                None)

            plan = SUBSCRIPTION_PLANS[plan_id] or {}

            # Get the image url of the product
            product = stripe.Product.retrieve(last_subscription.plan.product)
            image_url = product.images[0] if product.images and len(product.images) > 0 else None

            return {
                'credits_remaining': company.credit_balance,
                'flex_credits_remaining': company.flex_credit_balance,
                'plan': plan_id,
                "status": last_subscription.status,
                "seats": plan.get("seats", 0),
                "canceled_at": last_subscription.canceled_at if hasattr(last_subscription, 'canceled_at') else None,
                "seats_taken": Users.count_users_by_company_id(user.company_id),
                "image_url": image_url
            }

        subscription = active_subscriptions.data[0]

        price_id = subscription.plan.id

        plan_id = next((plan for plan, details in SUBSCRIPTION_PLANS.items() if details.get("stripe_price_id") == price_id), None)

        plan = SUBSCRIPTION_PLANS[plan_id] or {}

        # Get the image url of the product
        product = stripe.Product.retrieve(subscription.plan.product)
        image_url = product.images[0] if product.images and len(product.images) > 0 else None

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
            "seats_taken": Users.count_users_by_company_id(user.company_id),
            "auto_recharge": company.auto_recharge,
            "image_url": image_url
        }
    except Exception as e:
        print(f"Error getting subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get all available subscription plans
@router.get("/subscription-plans/")
async def get_subscription_plans(user=Depends(get_verified_user)):
    company = Companies.get_company_by_id(user.company_id)

    if company.subscription_not_required:
        return []

    """Get all available subscription plans"""
    plans = []
    for plan_id, plan_details in SUBSCRIPTION_PLANS.items():
        plans.append(SubscriptionPlanResponse(
            id=plan_id,
            price=plan_details["price"],
            credits_per_month=plan_details["credits_per_month"],
            seats=plan_details["seats"]
        ))

    return plans


@router.post("/checkout-webhook")
async def checkout_webhook(request: Request, stripe_signature: str = Header(None)):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="No Stripe signature provided")

    payload = await request.body()
    try:
        # Verify Stripe Webhook Signature
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=webhook_secret
        )

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        # Subscription events
        if event_type == "customer.subscription.created":
            handle_subscription_created(event_data)
            return
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(event_data)
            return
        elif event_type == "charge.succeeded":
            handle_charge_succeeded(event_data)
            return
        elif event_type == "invoice.paid":
            handle_invoice_paid(event_data)
            return
        else:
            print(f"Unhandled Stripe event type: {event_type}")

        return {"message": "Webhook processed successfully"}

    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        print(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _update_company_credits_from_subscription(event_data, action_description, is_invoice=False):
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
        plan_id = next((plan for plan, details in SUBSCRIPTION_PLANS.items() 
                       if details.get("stripe_price_id") == price_id), None)
        
        if not plan_id or plan_id not in SUBSCRIPTION_PLANS:
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
                print(f"Invalid custom_credit_amount in metadata: {custom_credit_amount}, falling back to plan default")
                credits_per_month = SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)
        else:
            # Get the credits per month for this plan
            credits_per_month = SUBSCRIPTION_PLANS[plan_id].get("credits_per_month", 0)
        
        # Add the credits to the company's balance
        if credits_per_month > 0:
            # Update the company's credit balance
            Companies.update_company_by_id(company.id, {
                "credit_balance": credits_per_month,
                "budget_mail_80_sent": False,
                "budget_mail_100_sent": False
            })
            
            credit_source = "custom metadata" if custom_credit_amount else "plan default"
            print(f"{action_description.capitalize()} {credits_per_month} credits to company {company.id} for subscription {subscription_id} (source: {credit_source})")

        try:
            crm_service.update_company_plan(company_name=company.name, plan=plan_id.replace("_", " ").title())
            crm_service.update_company_last_subscription_renewal_date(company_name=company.name, renewal_date=strftime('%Y-%m-%d'))
            crm_service.update_company_credit_consumption(company_name=company.name, credit_consumption=0.0, reset=True)

            company_users = Users.get_users_by_company_id(company_id=company.id)
            for user in company_users:
                crm_service.update_user_credit_usage(user_email=user.email, credit_usage=0.0, reset=True)
        except Exception as e:
            print(f"Failed to update CRM for company {company.name}: {e}")

        return company, credits_per_month, plan_id
        
    except Exception as e:
        print(f"Error {action_description} subscription event: {e}")
        return None, None, None


def handle_invoice_paid(event_data):
    """
    Handle invoice paid webhook event from Stripe.
    Updates company credit balance based on the subscription plan.
    
    Args:
        event_data: The invoice data from the Stripe webhook event
    """
    try:
        _update_company_credits_from_subscription(event_data, "adding from periodically paid invoice", is_invoice=True)
    except Exception as e:
        print(f"Error handling invoice paid event: {e}")


# For flex credits recharge
def handle_charge_succeeded(event_data):
    try:
        flex_credits_recharge = event_data.get("metadata", {}).get("flex_credits_recharge")

        if flex_credits_recharge == "true":
            company_id = event_data.get("metadata", {}).get("company_id")
            amount = event_data.get("amount")

            Companies.add_flex_credit_balance(company_id, float(amount) / 100) # Convert cents into Euros
    except Exception as e:
        print(f"Error processing charge succeeded event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def handle_subscription_created(event_data):
    """
    Handle subscription created webhook event from Stripe.
    Updates company credit balance based on the subscription plan.
    
    Args:
        event_data: The subscription data from the Stripe webhook event
    """
    try:
        _update_company_credits_from_subscription(event_data, "adding")
    except Exception as e:
        print(f"Error handling subscription created event: {e}")


def handle_subscription_updated(event_data):
    """
    Handle subscription updated webhook event from Stripe.
    Updates company credit balance based on the subscription plan.
    
    Args:
        event_data: The subscription data from the Stripe webhook event
    """
    try:
        _update_company_credits_from_subscription(event_data, "updating")
    except Exception as e:
        print(f"Error handling subscription updated event: {e}")


class UpdateAutoRechargeRequest(BaseModel):
    auto_recharge: bool

@router.post("/update-auto-recharge/")
async def update_auto_recharge(request: UpdateAutoRechargeRequest, user=Depends(get_verified_user)):
    try:
        result = Companies.update_auto_recharge(user.company_id, request.auto_recharge)
        if result:
            return {"message": f"Auto-recharge {'enabled' if request.auto_recharge else 'disabled'} successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to update auto-recharge setting")
    except Exception as e:
        print(f"Error updating auto-recharge: {e}")
        raise HTTPException(status_code=500, detail="Failed to update auto-recharge setting")

@router.post("/recharge-flex-credits/")
async def recharge_flex_credits(user=Depends(get_verified_user)):
    """
    Recharge flex credits for a company using their default payment method.

    Args:
        user: The user requesting the recharge

    Returns:
        dict: Information about the payment intent

    Raises:
        HTTPException: If there's an error with the payment or recharge process
    """
    try:
        company = Companies.get_company_by_id(user.company_id)

        # Check if the company has_active_subscription
        subscriptions = stripe.Subscription.list(
            customer=company.stripe_customer_id,
            status='active',
            limit=1
        )

        if not company.subscription_not_required and (not subscriptions or len(subscriptions.data) == 0):
            raise HTTPException(status_code=400, detail="No active subscription found. Please subscribe first.")

        # Get the customer's payment methods
        payment_methods = stripe.PaymentMethod.list(
            customer=company.stripe_customer_id,
            type="card"
        )

        # Check if the customer has any payment methods
        if not payment_methods or len(payment_methods.data) == 0:
            raise HTTPException(
                status_code=400,
                detail="No payment method found. Please add a payment method in your billing settings."
            )

        # Use the first payment method
        default_payment_method = payment_methods.data[0].id

        # Create a PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS,  # Default price in cents (25 euro)
            currency="eur",
            customer=company.stripe_customer_id,
            payment_method=default_payment_method,  # Specify the payment method
            payment_method_types=["card"],
            off_session=True,
            confirm=True,
            metadata={
                "company_id": company.id,
                "flex_credits_recharge": "true",
                "amount": FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS
            }
        )

        return {"message": "Credits recharged successfully", "payment_intent": payment_intent.id}

    except stripe.error.CardError as e:
        # Card declined
        print(f"Error recharging credits: {e}")
        raise HTTPException(status_code=400, detail=f"Card declined: {e.error.message}")
    except Exception as e:
        print(f"Error recharging credits: {e}")
        raise HTTPException(status_code=500, detail="Failed to recharge credits")