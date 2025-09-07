import os

import requests


class CRMService:
    def __init__(self):
        self.base_url = "https://api.attio.com/v2"
        self.headers = {
            "Authorization": f"Bearer {os.getenv("ATTIO_API_KEY")}",
            "Content-Type": "application/json",
        }
        self.timeout = 10

    def list_companies(self) -> list:
        response = requests.post(
            f"{self.base_url}/objects/companies/records/query",
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def create_company(self, name: str) -> dict:
        response = requests.post(
            f"{self.base_url}/objects/companies/records",
            headers=self.headers,
            json={
                "data": {
                    "values": {
                        "fd5db344-aaa7-403b-a94a-c374788a0c5e": name,
                        "1681a8cd-2bbd-4d31-abac-b187186f9486": f"{name} is an awesome company",
                    }
                }
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


crm_service = CRMService()

# companies = crm_service.list_companies()
# print(companies)

# new_company = crm_service.create_company("another company")
# print(new_company)
