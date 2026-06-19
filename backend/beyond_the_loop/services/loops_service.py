import logging
import requests
import os

from beyond_the_loop.models.users import UserModel
from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)


class LoopsService:

    def __init__(self):
        self.api_key = os.getenv("LOOPS_API_KEY")
        self.api_url = os.getenv("LOOPS_API_URL")

    @staticmethod
    def _resolve_language(user: UserModel) -> str:
        """Normalize the user's UI locale to a Loops language code.

        Falls back to "de" when nothing is stored — matches the one-shot
        bulk-sync default for existing users.
        """
        locale = None
        try:
            settings = user.settings
            if settings is not None:
                ui = settings.ui if isinstance(settings.ui, dict) else {}
                locale = ui.get("locale")
        except Exception:
            locale = None

        if not locale:
            return "de"
        return locale.split("-")[0].lower()

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
            except Exception:
                plan = "None"
        else:
            plan = "free"

        payload = {
            "id": existing_contact.json()[0].get("id") if existing_contact.json() else None,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "userGroup": user.role.capitalize(),
            "userId": user.id,
            "plan": plan,
            "language": self._resolve_language(user),
        }

        try:
            response = requests.post(self.api_url + "/contacts/update", json=payload, headers=headers)
        except Exception as e:
            raise Exception("Error in Loops contact update", e)

        if not response.json().get("success"):
            raise Exception(response.json())

    def mark_contact_deleted(self, email: str):
        """Mark a Loops contact as Deleted via userGroup, instead of removing it.

        Lets us keep historical reports/audiences intact while excluding the
        contact from any active-user segments.
        """
        if not os.getenv("LOOPS_SYNC", "false") == "true":
            return

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"email": email, "userGroup": "Deleted"}

        try:
            response = requests.post(
                self.api_url + "/contacts/update", json=payload, headers=headers
            )
            if not response.json().get("success"):
                log.warning(
                    f"Loops mark_contact_deleted failed for {email}: {response.text}"
                )
        except Exception as e:
            log.warning(f"Loops mark_contact_deleted exception for {email}: {e}")

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