"""Sync Current Data With Attio

Revision ID: cc5f9d52db2b
Revises: 41f6c14e7cf5
Create Date: 2025-09-21 18:33:02.741820

"""
import os
from typing import Sequence, Union
import time

import requests
import datetime

from alembic import op
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'cc5f9d52db2b'
down_revision: Union[str, None] = '41f6c14e7cf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

execute = os.getenv('ATTIO_SYNC_DATA', 'false').lower() == 'true'

# Attio rate limiting configuration
MAX_REQUESTS_PER_SECOND = 20
last_request_time = 0
request_count = 0

def rate_limit():
    global last_request_time, request_count
    current_time = time.time()

    if current_time - last_request_time >= 1.0:
        request_count = 0
        last_request_time = current_time

    if request_count >= MAX_REQUESTS_PER_SECOND:
        sleep_time = 1.0 - (current_time - last_request_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
        request_count = 0
        last_request_time = time.time()

    request_count += 1

def make_attio_request(method, url, headers, json_data):
    rate_limit()

    if method.upper() == 'POST':
        return requests.post(url, headers=headers, json=json_data, timeout=5)
    elif method.upper() == 'GET':
        return requests.get(url, headers=headers, timeout=5)
    return None

def upgrade() -> None:
    if not execute:
        print("ATTIO_SYNC_DATA is not set to 'true'. Skipping data sync with Attio.")
        return

    print("Starting data sync with Attio...")

    base_url = f"{os.getenv('ATTIO_API_BASE_URL')}"
    headers = {"Authorization": f"Bearer {os.getenv('ATTIO_API_KEY')}", "Content-Type": "application/json"}

    connection = op.get_bind()

    # fetch all companies from the local database
    companies = connection.execute(sqlalchemy.text("SELECT id, name FROM company"))

    for company in companies:
        company_id = company[0]
        company_name = company[1]
        created_at = connection.execute(
            sqlalchemy.text("SELECT created_at FROM user WHERE company_id = :company_id ORDER BY created_at ASC LIMIT 1"),
            {"company_id": company_id}
        ).fetchone()[0]
        
        print(f"Syncing data for company: {company_name} with ID: {company_id} and created at {created_at}")

        company_attio = None
        try:
            response = make_attio_request(
                'POST',
                f"{base_url}/objects/companies/records/query",
                headers,
                {"filter": {"name": company_name}}
            )
            if response.status_code == 200:
                response_data = response.json().get("data", [])

                if len(response_data) == 0:
                    response = make_attio_request(
                        'POST',
                        f"{base_url}/objects/companies/records",
                        headers,
                        {"data": {"values": {
                            "adoption_rate": [{"value": 0.0}],
                            "credit_consumption": [{"value": 0.0}],
                            "name": [{"value": company_name}],
                            "sign_up_date": [{"value": datetime.datetime.fromtimestamp(created_at, datetime.UTC).strftime('%Y-%m-%d')}]
                        }}}
                    )
                    if response.status_code == 200:
                        company_attio = response.json().get("data", None)

                elif len(response_data) >= 1:
                    print(f"Company {company_name} already exists in Attio, skipping creation.")
                    company_attio = response_data[0]

        except Exception as e:
            print(f"Error querying Attio for company {company_name}: {e}")
            continue

        if not company_attio:
            print(f"Attio company record is None for {company_name}, skipping user sync.")
            continue

        # fetch all users associated with the company
        users = connection.execute(
            sqlalchemy.text("SELECT email, role, first_name, last_name FROM user WHERE company_id = :company_id"),
            {"company_id": company_id}
        )

        attio_company_id = company_attio["id"]["record_id"]
        for user in users:
            user_email = user[0]
            user_role = user[1]
            user_firstname = user[2]
            user_lastname = user[3]

            print(f"Syncing data for user {user_firstname} {user_lastname} with email: {user_email} and role: {user_role}")

            try:
                response = make_attio_request(
                    'POST',
                    f"{base_url}/objects/people/records/query",
                    headers,
                    {"filter": {"email_addresses": user_email}}
                )
                if response.status_code == 200:
                    response_data = response.json().get("data", [])

                    if len(response_data) == 0:
                        response = make_attio_request(
                            'POST',
                            f"{base_url}/objects/people/records",
                            headers,
                            {"data": {"values": {
                                "access_level": user_role.capitalize(),
                                "company": [{"target_object": "companies", "target_record_id": attio_company_id}],
                                "credit_usage": [{"value": 0.0}],
                                "email_addresses": [user_email],
                                "name": [{"first_name": user_firstname, "last_name": user_lastname, "full_name": f"{user_firstname} {user_lastname}"}],
                            }}}
                        )
                        print(f"Create user response status: {response.status_code}, response text: {response.text}")

                    elif len(response_data) >= 1:
                        print(f"User {user_email} already exists in Attio, skipping creation.")

            except Exception as e:
                print(f"Error querying Attio for user {user_email}: {e}")
                continue

def downgrade() -> None:
    pass
