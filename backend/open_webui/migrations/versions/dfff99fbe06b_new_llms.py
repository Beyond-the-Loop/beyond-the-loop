"""New LLMs

Revision ID: dfff99fbe06b
Revises: 6964fbec2a16
Create Date: 2025-11-26 15:29:47.410062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy
import uuid
import json
import datetime


# revision identifiers, used by Alembic.
revision: str = 'dfff99fbe06b'
down_revision: Union[str, None] = '6964fbec2a16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    new_models = {
        "GPT-5.1 (instant)": {
            "cost": {
                "cost_per_million_input_tokens": 1.25,
                "cost_per_million_output_tokens": 10,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
        },
        "GPT-5.1 (thinking)": {
            "cost": {
                "cost_per_million_input_tokens": 1.25,
                "cost_per_million_output_tokens": 10,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
        }
    }

    companies = connection.execute(sqlalchemy.text("SELECT id FROM company")).fetchall()

    for new_model_name, new_model_data in new_models.items():
        model_cost = new_model_data["cost"]
        connection.execute(
            sqlalchemy.text(
                """INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries) VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)"""
            ),
            {
                "model_name": new_model_name,
                "cost_per_million_input_tokens": model_cost[
                    "cost_per_million_input_tokens"
                ],
                "cost_per_million_output_tokens": model_cost[
                    "cost_per_million_output_tokens"
                ],
                "cost_per_image": model_cost["cost_per_image"],
                "cost_per_minute": model_cost["cost_per_minute"],
                "cost_per_million_characters": model_cost[
                    "cost_per_million_characters"
                ],
                "cost_per_million_reasoning_tokens": model_cost[
                    "cost_per_million_reasoning_tokens"
                ],
                "cost_per_thousand_search_queries": model_cost[
                    "cost_per_thousand_search_queries"
                ],
            },
        )

        # add new models to companies
        for company in companies:
            company_id = company[0]

            existing_model = connection.execute(
                sqlalchemy.text("SELECT COUNT(*) FROM model WHERE name = :name AND company_id = :company_id"),
                {"name": new_model_name, "company_id": company_id}).scalar()

            if existing_model == 0:
                connection.execute(
                    sqlalchemy.text(
                        "INSERT INTO model (id, name, meta, params, created_at, updated_at, is_active, company_id) VALUES (:id, :name, :meta, :params, :created_at, :updated_at, :is_active, :company_id)"),
                    {
                        "id": str(uuid.uuid4()),
                        "name": new_model_name,
                        "meta": json.dumps(new_model_data["meta"]),
                        "params": json.dumps(new_model_data["params"]),
                        "created_at": int(datetime.datetime.now().timestamp()),
                        "updated_at": int(datetime.datetime.now().timestamp()),
                        "is_active": True,
                        "company_id": company_id,
                    },
                )

        # set user_id to null for all base models
        connection.execute(sqlalchemy.text("UPDATE model SET user_id = NULL WHERE base_model_id IS NULL"))

def downgrade() -> None:
    pass
