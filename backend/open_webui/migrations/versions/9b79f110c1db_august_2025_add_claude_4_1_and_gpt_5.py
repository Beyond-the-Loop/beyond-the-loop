"""August 2025 add Claude 4.1 and GPT-5

Revision ID: 9b79f110c1db
Revises: 3572e4045c21
Create Date: 2025-08-10 18:52:34.881878

"""

from typing import Sequence, Union

from alembic import op
import datetime
import uuid
import json
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = "9b79f110c1db"
down_revision: Union[str, None] = "3572e4045c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    new_models_list = {
        "Claude Opus 4.1": {
            "cost": {
                "cost_per_million_input_tokens": 15,
                "cost_per_million_output_tokens": 75,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
            "is_active": 0,
        },
        "GPT-5": {
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
            "replace_with": None,
            "stats": "add",
            "visibility": "show",
            "is_active": 1,
        },
    }

    # add models into model_cost table
    for model_name, model_data in new_models_list.items():
        model_cost = model_data["cost"]
        
        # Check if model already exists to avoid UNIQUE constraint error
        existing_model = connection.execute(sqlalchemy.text("SELECT COUNT(*) FROM model_cost WHERE model_name = :model_name"),{"model_name": model_name}).scalar()
        
        if existing_model == 0:
            sql_statement = sqlalchemy.text("INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries) VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)")
        else:
            sql_statement = sqlalchemy.text("UPDATE model_cost SET cost_per_million_input_tokens = :cost_per_million_input_tokens, cost_per_million_output_tokens = :cost_per_million_output_tokens, cost_per_image = :cost_per_image, cost_per_minute = :cost_per_minute, cost_per_million_characters = :cost_per_million_characters, cost_per_million_reasoning_tokens = :cost_per_million_reasoning_tokens, cost_per_thousand_search_queries = :cost_per_thousand_search_queries WHERE model_name = :model_name")

        connection.execute(
            sql_statement,
            {
                "model_name": model_name,
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

    # add missing models to companies
    companies = connection.execute(sqlalchemy.text("SELECT id FROM company")).fetchall()
    for company in companies:
        company_id = company[0]

        for model_name, model_data in new_models_list.items():
            existing_model = connection.execute(sqlalchemy.text("SELECT COUNT(*) FROM model WHERE name = :name AND company_id = :company_id"),{"name": model_name, "company_id": company_id}).scalar()
            
            if existing_model == 0:
                connection.execute(
                    sqlalchemy.text(
                        "INSERT INTO model (id, name, meta, params, created_at, updated_at, is_active, company_id) VALUES (:id, :name, :meta, :params, :created_at, :updated_at, :is_active, :company_id)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "name": model_name,
                        "meta": json.dumps(model_data["meta"]),
                        "params": json.dumps(model_data["params"]),
                        "created_at": int(datetime.datetime.now().timestamp()),
                        "updated_at": int(datetime.datetime.now().timestamp()),
                        "is_active": model_data["is_active"],
                        "company_id": company_id,
                    },
                )


def downgrade() -> None:
    pass
