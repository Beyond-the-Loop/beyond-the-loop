import stripe
from pydantic import BaseModel
from fastapi import Depends, HTTPException, Request, Header, APIRouter
import os
from typing import Optional

from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.users import Users
from open_webui.utils.auth import get_verified_user
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.services.crm_service import crm_service

router = APIRouter()

class SubscriptionPlanResponse(BaseModel):
    """Response model for subscription plans"""
    id: str
    price: Optional[int] = None
    credits_per_month: Optional[int] = None
    seats: Optional[int] = None

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

        configuration = payments_service.PREMIUM_BILLING_PORTAL_ID if payments_service.get_subscription(company.id).get("plan") == "premium" else None

        # Create a billing portal session
        session = stripe.billing_portal.Session.create(
            customer=company.stripe_customer_id,
            configuration=configuration,
            return_url=os.getenv('FRONTEND_BASE_URL') + "?modal=company-settings&tab=billing",
        )

        return {"url": session.url}
    except Exception as e:
        print(f"Error creating billing portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get current subscription details
@router.get("/subscription/")
def get_subscription(user=Depends(get_verified_user)):
    return payments_service.get_subscription(user.company_id)

# Get all available subscription plans
@router.get("/subscription-plans/")
async def get_subscription_plans(user=Depends(get_verified_user)):
    """Get all available subscription plans"""
    plans = []
    for plan_id, plan_details in payments_service.SUBSCRIPTION_PLANS.items():
        plans.append(SubscriptionPlanResponse(
            id=plan_id,
            price=plan_details.get("price", None),
            credits_per_month=plan_details.get("credits_per_month", None),
            seats=plan_details.get("seats", None),
        ))

    return plans


@router.get("/create-premium-subscription-checkout-session/")
def create_premium_subscription_checkout_session(user=Depends(get_verified_user)):
    company = Companies.get_company_by_id(user.company_id)

    checkout_session = stripe.checkout.Session.create(
        automatic_tax={
            "enabled": True,
        },
        tax_id_collection={
            "enabled": True
        },
        customer_update={
            "address": "auto",
            "name": "auto",
        },
        customer=company.stripe_customer_id,
        line_items=[{
            "price": payments_service.SUBSCRIPTION_PLANS.get("premium").get("stripe_price_id", ""),
            "quantity": Users.get_num_active_users_by_company_id(user.company_id),
        }],
        mode="subscription",
        success_url=os.getenv('FRONTEND_BASE_URL') + "?modal=company-settings&tab=billing",
        cancel_url=os.getenv('FRONTEND_BASE_URL') + "?modal=company-settings&tab=billing",
        ui_mode="hosted",
        billing_address_collection="required",
    )

    return {"url": checkout_session.url}


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
            secret=payments_service.webhook_secret
        )

        event_type = event.get("type")
        event_data = event.get("data", {}).get("object", {})

        # Subscription events
        if event_type == "customer.subscription.created":
            handle_subscription_created(event_data)
            return None
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(event_data)
            return None
        elif event_type == "charge.succeeded":
            handle_charge_succeeded(event_data)
            return None
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(event_data)
        else:
            print(f"Unhandled Stripe event type: {event_type}")

        return {"message": "Webhook processed successfully"}

    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        print(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy subscription created
def handle_subscription_created(event_data):
    """
    Handle subscription created webhook event from Stripe.
    Updates company credit balance based on the subscription plan.

    Args:
        event_data: The subscription data from the Stripe webhook event
    """
    try:
        payments_service.handle_company_subscription_update(event_data)
    except Exception as e:
        print(f"Error handling subscription created event: {e}")


# Legacy subscription updated
def handle_subscription_updated(event_data):
    """
    Handle subscription updated webhook event from Stripe.
    Updates company credit balance based on the subscription plan.

    Args:
        event_data: The subscription data from the Stripe webhook event
    """
    try:
        payments_service.handle_company_subscription_update(event_data)
    except Exception as e:
        print(f"Error handling subscription updated event: {e}")


def handle_subscription_deleted(event_data):
    try:
        # Extract subscription details
        subscription_id = event_data.get('id')

        stripe_customer_id = event_data.get('customer')

        if not subscription_id or not stripe_customer_id:
            print("Missing subscription_id or customer_id in event data")
            return

        # Get the company associated with this Stripe customer
        company = Companies.get_company_by_stripe_customer_id(stripe_customer_id)

        crm_service.update_company_plan(company.name, "Free")
    except Exception as e:
        print(f"Error handling subscription deleted event: {e}")


# Legacy flex credits recharge
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


class UpdateAutoRechargeRequest(BaseModel):
    auto_recharge: bool

@router.post("/update-auto-recharge/")
async def update_auto_recharge(request: UpdateAutoRechargeRequest, user=Depends(get_verified_user)):
    try:
        subscription = payments_service.get_subscription(user.company_id)

        if subscription.get("plan") == "free" or subscription.get("plan") == "premium":
            raise HTTPException(status_code=403, detail="Failed to update auto-recharge setting: Not available for Free or Premium companies")

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
        subscription = payments_service.get_subscription(user.company_id)

        if subscription.get("plan") == "free" or subscription.get("plan") == "premium":
            raise HTTPException(status_code=403, detail="Failed to update auto-recharge setting: Not available for Free or Premium companies")

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
            amount=payments_service.FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS,  # Default price in cents (25 euro)
            currency="eur",
            customer=company.stripe_customer_id,
            payment_method=default_payment_method,  # Specify the payment method
            payment_method_types=["card"],
            off_session=True,
            confirm=True,
            metadata={
                "company_id": company.id,
                "flex_credits_recharge": "true",
                "amount": payments_service.FLEX_CREDITS_DEFAULT_PRICE_IN_CENTS
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