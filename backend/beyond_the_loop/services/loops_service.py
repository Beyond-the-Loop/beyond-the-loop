import requests
import os

from beyond_the_loop.models.users import UserModel
from beyond_the_loop.models.users import Users
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.models.companies import Companies


class LoopsService:

    def __init__(self):
        self.api_key = os.getenv("LOOPS_API_KEY")
        self.api_url = os.getenv("LOOPS_API_URL")

    def create_or_update_loops_contact(
            self,
            user: UserModel
    ):
        if not os.getenv("LOOPS_SYNC", "false") == "true":
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        find_contact_params = {
            "email": user.email
        }

        try:
            existing_contact = requests.get(self.api_url + "/contacts/find", params=find_contact_params, headers=headers)
        except Exception as e:
            raise Exception("Error in Loops contact find", e)

        # On user signup no company is assigned
        if user.company_id not in ["NEW", "NO_COMPANY"]:
            try:
                subscription_details = payments_service.get_subscription(user.company_id)
                plan = subscription_details.get("plan")
                subscribed = plan == "unlimited" or subscription_details.get("status") == "active" and not subscription_details.get("cancel_at_period_end")
            except Exception:
                plan = "None"
                subscribed = False
        else:
            plan = next(iter(payments_service.SUBSCRIPTION_PLANS.keys()))
            subscribed = False

        payload = {
            "id": existing_contact.json()[0].get("id") if existing_contact.json() else None,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "userGroup": user.role.capitalize(),
            "subscribed": subscribed,
            "userId": user.id,
            "plan": plan
        }

        try:
            response = requests.post(self.api_url + "/contacts/update", json=payload, headers=headers)
        except Exception as e:
            raise Exception("Error in Loops contact update", e)

        if not response.json().get("success"):
            raise Exception(response.json())

    def update_company_users_loops_contact(self, event_data):
        stripe_customer_id = event_data.get('customer')

        if not stripe_customer_id:
            print("Missing customer_id in event data in company users loops update")
            return

        # Get the company associated with this Stripe customer
        company = Companies.get_company_by_stripe_customer_id(stripe_customer_id)

        if not company:
            print("Company not found in event data in company users loops update")
            return

        users = Users.get_users_by_company_id(company.id)

        for user in users:
            loops_service.create_or_update_loops_contact(user)

    def send_transactional_email(
            self,
            email: str,
            transactional_id: str,
            add_to_audience: bool = False,
            data_variables: dict = None,
            attachments: list = None,
    ):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "email": email,
            "transactionalId": transactional_id,
            "addToAudience": add_to_audience,
            "dataVariables": data_variables or {},
            "attachments": attachments or []
        }

        response = requests.post(self.api_url + "/transactional", json=payload, headers=headers)

        if not response.json().get("success"):
            raise Exception(response.json())

loops_service = LoopsService()