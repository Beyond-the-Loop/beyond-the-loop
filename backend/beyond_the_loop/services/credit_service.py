import math

import stripe
from typing import Optional
from fastapi import HTTPException

from beyond_the_loop.models.users import Users
from beyond_the_loop.models.companies import Companies, EIGHTY_PERCENT_CREDIT_LIMIT
from beyond_the_loop.services.email_service import EmailService
from beyond_the_loop.models.model_costs import ModelCosts
from beyond_the_loop.routers.payments import FLEX_CREDITS_DEFAULT_PRICE, FLEX_CREDITS_DEFAULT_AMOUNT

PROFIT_MARGIN_FACTOR = 1.5
COSTS_PER_CREDIT = (FLEX_CREDITS_DEFAULT_PRICE / 100) / FLEX_CREDITS_DEFAULT_AMOUNT

class CreditService:
    def __init__(self):
        """Initialize the CreditService."""
        pass

    async def subtract_credits_by_user_and_credits(self, user, credit_cost: int):
        """
        Subtract credits from a company's balance and handle low balance scenarios.
        
        Args:
            user: The user making the request
            credit_cost: The number of credits to subtract
            
        Returns:
            Total credit cost
        """

        # Get current balance
        current_balance = Companies.get_credit_balance(user.company_id)
        
        # Check 80% threshold
        if current_balance - credit_cost < EIGHTY_PERCENT_CREDIT_LIMIT:  # If balance is less than 125% of required (which means we're below 80%)
            should_send_budget_email_80 = True  # Default to sending email

            company = Companies.get_company_by_id(user.company_id)

            if Companies.get_auto_recharge(user.company_id):
                try:
                    # Check if the company has a stripe customer ID and payment method before recharging
                    if not company.stripe_customer_id:
                        print(f"Auto-recharge failed: No stripe customer ID for company {user.company_id}")
                        # Don't attempt to recharge if there's no stripe customer ID
                    else:
                        # Check if the customer has any payment methods
                        try:
                            payment_methods = stripe.PaymentMethod.list(
                                customer=company.stripe_customer_id,
                                type="card"
                            )

                            if not payment_methods or len(payment_methods.data) == 0:
                                print(
                                    f"Auto-recharge failed: No payment methods found for company {user.company_id}")
                                # Don't attempt to recharge if there are no payment methods
                            else:
                                # Trigger auto-recharge using the charge_customer endpoint
                                await self.recharge_flex_credits(user)
                                # Note: The webhook will handle adding the credits when payment succeeds
                                should_send_budget_email_80 = False  # Don't send email if auto-recharge succeeded
                        except Exception as e:
                            print(f"Error checking payment methods: {str(e)}")
                except HTTPException as e:
                    print(f"Auto-recharge failed: {str(e)}")
                except Exception as e:
                    print(f"Unexpected error during auto-recharge: {str(e)}")

            if should_send_budget_email_80 and not company.budget_mail_80_sent:
                admins = Users.get_admin_users_by_company(company.id)

                for admin in admins:
                    email_service = EmailService()
                    email_service.send_budget_mail_80(to_email=admin.email,
                                                    recipient_name=admin.first_name + " " + admin.last_name)

                Companies.update_company_by_id(company.id, {"budget_mail_80_sent": True})

        # Subtract credits from balance
        Companies.subtract_credit_balance(user.company_id, credit_cost)

        return credit_cost

    async def subtract_credits_by_user_for_image(self, user, model_name: str):
        print("model naaaame", model_name)

        image_cost = ModelCosts.get_cost_per_image_by_model_name(model_name) * PROFIT_MARGIN_FACTOR

        credit_cost = math.ceil(image_cost / COSTS_PER_CREDIT)
        print("credit cost", credit_cost)

        return await self.subtract_credits_by_user_and_credits(user, credit_cost)

    async def subtract_credits_by_user_and_tokens(self, user, model_name: str, input_tokens: int, output_tokens: int, reasoning_tokens: int, with_search_query_cost: bool):
        costs_per_input_token = ModelCosts.get_cost_per_million_input_tokens_by_model_name(model_name) / 1000000
        cost_per_output_token = ModelCosts.get_cost_per_million_output_tokens_by_model_name(model_name) / 1000000

        if output_tokens > 0:
            cost_per_reasoning_token = ModelCosts.get_cost_per_million_output_tokens_by_model_name(model_name) / 1000000
        else:
            cost_per_reasoning_token = 0

        if with_search_query_cost:
            search_query_cost = ModelCosts.get_cost_per_thousand_search_queries_by_model_name(model_name) / 1000
        else:
            search_query_cost = 0

        total_costs = (input_tokens * costs_per_input_token + output_tokens * cost_per_output_token + reasoning_tokens * cost_per_reasoning_token + search_query_cost) * PROFIT_MARGIN_FACTOR

        print("COST PER CREDIT", COSTS_PER_CREDIT)

        credit_cost = math.ceil(total_costs / COSTS_PER_CREDIT)

        print(f" Model: {model_name}", f"Reasoning tokens: {reasoning_tokens}", f"Search query cost: {search_query_cost}", f"Credit cost: {credit_cost}", f"Cost per input token: {costs_per_input_token}", f"Cost per output token: {cost_per_output_token}", f"Total costs: {total_costs}", f"Input tokens: {input_tokens}", f"Output tokens: {output_tokens}")

        return await self.subtract_credits_by_user_and_credits(user, credit_cost)

    async def recharge_flex_credits(self, user):
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
            
            if not company.stripe_customer_id:
                raise HTTPException(status_code=400, detail="No payment method found. Please add a payment method first.")
            
            # Retrieve the customer to check for payment methods
            customer = stripe.Customer.retrieve(company.stripe_customer_id)
            
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
                amount=2500,  # Default price in cents (25 euro)
                currency="eur",
                customer=company.stripe_customer_id,
                payment_method=default_payment_method,  # Specify the payment method
                payment_method_types=["card"],
                off_session=True,
                confirm=True,
                metadata={
                    "company_id": company.id,
                    "user_id": user.id,
                    "user_email": user.email,
                    "recharge_type": "auto" if Companies.get_auto_recharge(user.company_id) else "manual",
                    "flex_credits_recharge": "true"
                }
            )
            
            return {"message": "Credits recharged successfully", "payment_intent": payment_intent.id}
            
        except stripe.error.CardError as e:
            # Card declined
            raise HTTPException(status_code=400, detail=f"Card declined: {e.error.message}")
        except Exception as e:
            print(f"Error recharging credits: {e}")
            raise HTTPException(status_code=500, detail="Failed to recharge credits")

    def get_credit_balance(self, company_id: str) -> Optional[int]:
        """
        Get the current credit balance for a company.
        
        Args:
            company_id: The ID of the company
            
        Returns:
            int: The current credit balance, or None if the company doesn't exist
        """
        return Companies.get_credit_balance(company_id)
