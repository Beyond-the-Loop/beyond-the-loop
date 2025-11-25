import logging
import os
from time import strftime
from cachetools import TTLCache
import requests

log = logging.getLogger(__name__)


class CRMService:
    def __init__(self):
        self.base_url = f"{os.getenv('ATTIO_API_BASE_URL')}"
        self.headers = {"Authorization": f"Bearer {os.getenv('ATTIO_API_KEY')}", "Content-Type": "application/json"}
        self.timeout = 5
        self.execute = os.getenv('ATTIO_SYNC_DATA', 'false').lower() == 'false'

        self._company_cache = TTLCache(maxsize=512, ttl=600)
        self._user_cache = TTLCache(maxsize=512, ttl=600)

    def get_company_by_company_name(self, company_name: str):
        if not self.execute:
            return None

        try:
            if company_name in self._company_cache:
                return self._company_cache[company_name]

            response = requests.post(
                f"{self.base_url}/objects/companies/records/query",
                headers=self.headers,
                json={"filter": {"name": company_name}},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                company = response.json().get("data", [])
                if len(company) == 1:
                    self._company_cache[company_name] = company[0]
                    return company[0]
                elif len(company) > 1:
                    log.warning(f"get_company_by_company_name unexpected number of records ({len(company)}) for {company_name}, expected 1.")

                return None

            log.warning(f"get_company_by_company_name failed for {company_name}, status code: {response.status_code}, and response: {response.text}")
            self._company_cache.pop(company_name, None)
            return None

        except Exception as e:
            log.error(f"get_company_by_company_name exception for {company_name}: {e}")
            return None

    def create_company(self, company_name: str):
        if not self.execute:
            return

        try:
            if self.get_company_by_company_name(company_name):
                log.warning(f"create_company skipped, company {company_name} already exists.")
                return

            response = requests.post(
                f"{self.base_url}/objects/companies/records",
                headers=self.headers,
                json={"data": {"values": {
                    "adoption_rate": [{"value": 0.0}],
                    "credit_consumption": [{"value": 0.0}],
                    "name": [{"value": company_name}],
                    "plan": "Starter Monthly",
                    "sign_up_date": [{"value": strftime("%Y-%m-%d")}],
                }}},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                company = response.json().get("data", None)
                self._company_cache[company_name] = company
                return

            log.warning(f"create_company failed for {company_name}, status code: {response.status_code}, and response: {response.text}")
            return

        except Exception as e:
            log.error(f"create_company exception for {company_name}: {e}")
            return

    def update_company_plan(self, company_name: str, plan: str):
        if not self.execute:
            return

        try:
            company = self.get_company_by_company_name(company_name)

            if company:
                record_id = company["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/companies/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {"plan": plan}}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    company = response.json().get("data", None)
                    self._company_cache[company_name] = company
                    return

                log.warning(f"update_company_plan failed for {company_name}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_company_plan exception for {company_name}: {e}")
            return

    def update_company_adoption_rate(self, company_name: str, adoption_rate: float):
        if not self.execute:
            return

        try:
            company = self.get_company_by_company_name(company_name)

            if company:
                record_id = company["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/companies/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {"adoption_rate": adoption_rate}}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    company = response.json().get("data", None)
                    self._company_cache[company_name] = company
                    return

                log.warning(f"update_company_adoption_rate failed for {company_name}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_company_adoption_rate exception for {company_name}: {e}")
            return

    def update_company_credit_consumption(self, company_name: str, credit_consumption: float):
        if not self.execute:
            return

        try:
            company = self.get_company_by_company_name(company_name)

            if company:
                record_id = company["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/companies/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {"credit_consumption": credit_consumption}}},
                    timeout=self.timeout,
                )
                
                if response.status_code == 200:
                    company = response.json().get("data", None)
                    self._company_cache[company_name] = company
                    return

                log.warning(f"update_company_credit_consumption failed for {company_name}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_company_credit_consumption exception for {company_name}: {e}")
            return

    def update_company_last_subscription_renewal_date(self, company_name: str, renewal_date: str):
        if not self.execute:
            return

        try:
            company = self.get_company_by_company_name(company_name)

            if company:
                record_id = company["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/companies/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {
                        "credit_consumption": 0,
                        "last_subscription_renewal_date": renewal_date,
                    }}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    company = response.json().get("data", None)
                    self._company_cache[company_name] = company
                    return

                log.warning(f"update_company_last_subscription_renewal_date failed for {company_name}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_company_last_subscription_renewal_date exception for {company_name}: {e}")
            return

    def get_user_by_email(self, user_email: str):
        if not self.execute:
            return None

        try:
            if user_email in self._user_cache:
                return self._user_cache[user_email]
                
            response = requests.post(
                f"{self.base_url}/objects/people/records/query",
                headers=self.headers,
                json={"filter": {"email_addresses": user_email}},
                timeout=self.timeout,
            )
            
            if response.status_code == 200:
                user = response.json().get("data", [])
                if len(user) == 1:
                    self._user_cache[user_email] = user[0]
                    return user[0]
                elif len(user) > 1:
                    log.warning(f"get_user_by_email unexpected number of records ({len(user)}) for {user_email}, expected 1.")

                return None

            log.warning(f"get_user_by_email failed for {user_email}, status code: {response.status_code}, and response: {response.text}")
            self._user_cache.pop(user_email, None)
            return None

        except Exception as e:
            log.error(f"get_user_by_email exception for {user_email}: {e}")
            return None

    def create_user(self, company_name: str, user_email: str, user_firstname: str, user_lastname: str, access_level: str):
        if not self.execute:
            return

        try:
            if self.get_user_by_email(user_email):
                return
                
            company = self.get_company_by_company_name(company_name)

            if company:
                company_id = company["id"]["record_id"]

                response = requests.post(
                    f"{self.base_url}/objects/people/records",
                    headers=self.headers,
                    json={"data": {"values": {
                        "access_level": access_level.capitalize(),
                        "company": [{"target_object": "companies", "target_record_id": company_id}],
                        "credit_usage": [{"value": 0.0}],
                        "email_addresses": [user_email],
                        "name": [{"first_name": user_firstname, "last_name": user_lastname, "full_name": f"{user_firstname} {user_lastname}"}],
                    }}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    user = response.json().get("data", None)
                    self._user_cache[user_email] = user
                    return

                log.warning(f"create_user failed for {user_email}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"create_user exception for {user_email}: {e}")
            return

    def update_user_access_level(self, user_email: str, access_level: str):
        if not self.execute:
            return

        try:
            user = self.get_user_by_email(user_email)

            if user:
                record_id = user["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/people/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {"access_level": access_level.capitalize()}}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    user = response.json().get("data", None)
                    self._user_cache[user_email] = user
                    return

                log.warning(f"update_user_access_level failed for {user_email}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_user_access_level exception for {user_email}: {e}")
            return

    def update_user_credit_usage(self, user_email: str, credit_usage: float):
        if not self.execute:
            return

        try:
            user = self.get_user_by_email(user_email)

            if user:
                record_id = user["id"]["record_id"]
                response = requests.patch(
                    f"{self.base_url}/objects/people/records/{record_id}",
                    headers=self.headers,
                    json={"data": {"values": {"credit_usage": credit_usage}}},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    user = response.json().get("data", None)
                    self._user_cache[user_email] = user
                    return

                log.warning(f"update_user_credit_usage failed for {user_email}, status code: {response.status_code}, and response: {response.text}")

            return

        except Exception as e:
            log.error(f"update_user_credit_usage exception for {user_email}: {e}")
            return

crm_service = CRMService()
