import os
from time import strftime

import requests


class CRMService:
    def __init__(self):
        self.base_url = f"{os.getenv("ATTIO_API_BASE_URL")}"
        self.headers = {"Authorization": f"Bearer {os.getenv("ATTIO_API_KEY")}", "Content-Type": "application/json"}
        self.timeout = 10

    def create_company(self, company_name: str):
        if self.get_company_by_company_name(company_name):
            return
        requests.post(
            f"{self.base_url}/objects/companies/records",
            headers=self.headers,
            json={"data": {"values": {
                "name": [{"value": company_name}],
                "plan": "Free",
                "sign_up_date": [{"value": strftime("%Y-%m-%d")}],
                "adoption_rate": [{"value": 0.0}],
                "credit_consumption": [{"value": 0.0}],
            }}},
            timeout=self.timeout,
        )
        return

    def get_company_by_company_name(self, company_name: str):
        response = requests.post(
            f"{self.base_url}/objects/companies/records/query",
            headers=self.headers,
            json={"filter": {"name": company_name}},
            timeout=self.timeout,
        )
        company = response.json().get("data", [])
        return company if company else None

    def update_company_plan(self, company_name: str, plan: str):
        company = self.get_company_by_company_name(company_name)
        if company:
            record_id = company[0]["id"]["record_id"]
            requests.patch(
                f"{self.base_url}/objects/companies/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"plan": plan}}},
                timeout=self.timeout,
            )

    def update_company_signup_date(self, company_name: str, signup_date: str):
        company = self.get_company_by_company_name(company_name)
        if company:
            record_id = company[0]["id"]["record_id"]
            requests.patch(
                f"{self.base_url}/objects/companies/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"sign_up_date": signup_date}}},
                timeout=self.timeout,
            )

    def update_company_adoption_rate(self, company_name: str, adoption_rate: float):
        company = self.get_company_by_company_name(company_name)
        if company:
            record_id = company[0]["id"]["record_id"]
            requests.patch(
                f"{self.base_url}/objects/companies/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"adoption_rate": adoption_rate}}},
                timeout=self.timeout,
            )

    def update_company_credit_consumption(self, company_name: str, credit_consumption: float, reset: bool):
        company = self.get_company_by_company_name(company_name)
        if company:
            record_id = company[0]["id"]["record_id"]
            credits_used = (
                0
                if reset
                else company[0]["values"]["credit_consumption"][0]["value"]
                + credit_consumption
            )
            requests.patch(
                f"{self.base_url}/objects/companies/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"credit_consumption": credits_used}}},
                timeout=self.timeout,
            )

    def update_company_last_subscription_renewal_date(self, company_name: str, renewal_date: str):
        company = self.get_company_by_company_name(company_name)
        if company:
            record_id = company[0]["id"]["record_id"]
            requests.patch(
                f"{self.base_url}/objects/companies/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"last_subscription_renewal_date": renewal_date}}},
                timeout=self.timeout,
            )

    def create_user(self, company_name: str, user_email: str, user_firstname: str, user_lastname: str, access_level: str):
        if self.get_user_by_email(user_email):
            return
        company = self.get_company_by_company_name(company_name)
        if company:
            company_id = company[0]["id"]["record_id"]
            requests.post(
                f"{self.base_url}/objects/people/records",
                headers=self.headers,
                json={"data": {"values": {
                    "email_addresses": [user_email],
                    "name": [{"first_name": user_firstname, "last_name": user_lastname, "full_name": f"{user_firstname} {user_lastname}"}],
                    "company": [{"target_object": "companies", "target_record_id": company_id}],
                    "access_level": access_level,
                    "credit_usage": 0.0,
                }}},
                timeout=self.timeout,
            )
        return

    def get_user_by_email(self, user_email: str):
        response = requests.post(
            f"{self.base_url}/objects/people/records/query",
            headers=self.headers,
            json={"filter": {"email_addresses": user_email}},
            timeout=self.timeout,
        )
        user = response.json().get("data", [])
        return user if user else None

    def update_user_access_level(self, user_email: str, access_level: str):
        user = self.get_user_by_email(user_email)
        if user:
            record_id = user[0]["id"]["record_id"]
            requests.patch(
                f"{self.base_url}/objects/people/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"access_level": access_level}}},
                timeout=self.timeout,
            )

    def update_user_credit_usage(self, user_email: str, credit_usage: float, reset: bool):
        user = self.get_user_by_email(user_email)
        if user:
            record_id = user[0]["id"]["record_id"]
            credits_used = (
                0
                if reset
                else user[0]["values"]["credit_usage"][0]["value"]
                + credit_usage
            )
            requests.patch(
                f"{self.base_url}/objects/people/records/{record_id}",
                headers=self.headers,
                json={"data": {"values": {"credit_usage": credits_used}}},
                timeout=self.timeout,
            )


crm_service = CRMService()
