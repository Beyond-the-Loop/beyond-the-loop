"""october_2025_new_llms

Revision ID: 5eeb9eee6f05
Revises: cc5f9d52db2b
Create Date: 2025-10-12 13:54:01.202227

"""
from typing import Sequence, Union

from alembic import op
import datetime
import uuid
import json
import sqlalchemy
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '5eeb9eee6f05'
down_revision: Union[str, None] = 'cc5f9d52db2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # models data
    new_models_list = {
        "Claude Sonnet 4.5": {
            "cost": {
                "cost_per_million_input_tokens": 3,
                "cost_per_million_output_tokens": 15,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "visibility": "show",
            "is_active": 0,
        },
        "GPT-5 mini": {
            "cost": {
                "cost_per_million_input_tokens": 0.25,
                "cost_per_million_output_tokens": 2,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "visibility": "show",
            "is_active": 0,
        },
        "GPT-5 nano": {
            "cost": {
                "cost_per_million_input_tokens": 0.05,
                "cost_per_million_output_tokens": 0.4,
                "cost_per_image": None,
                "cost_per_minute": None,
                "cost_per_million_characters": None,
                "cost_per_million_reasoning_tokens": None,
                "cost_per_thousand_search_queries": None,
            },
            "meta": {},
            "params": {},
            "visibility": "show",
            "is_active": 0,
        },
    }
    legacy_models_list = {
        "Claude Sonnet 4": {
            "replace_with": "Claude Sonnet 4.5",
        },
        "GPT 4.1": {
            "replace_with": "GPT-5",
        },
        "GPT-4.1 mini": {
            "replace_with": "GPT-5 mini",
        },
        "GPT-4.1 nano": {
            "replace_with": "GPT-5 nano",
        },
    }
    # companies
    companies = connection.execute(sqlalchemy.text("SELECT id FROM company")).fetchall()

    # add new models to model_cost table
    for model_name, model_data in new_models_list.items():
        model_cost = model_data["cost"]

        # Check if model already exists to avoid UNIQUE constraint error
        existing_model = connection.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM model_cost WHERE model_name = :model_name"),
            {"model_name": model_name},
        ).scalar()

        sql_statement = (
            sqlalchemy.text("INSERT INTO model_cost (model_name, cost_per_million_input_tokens, cost_per_million_output_tokens, cost_per_image, cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens, cost_per_thousand_search_queries) VALUES (:model_name, :cost_per_million_input_tokens, :cost_per_million_output_tokens, :cost_per_image, :cost_per_minute, :cost_per_million_characters, :cost_per_million_reasoning_tokens, :cost_per_thousand_search_queries)")
            if existing_model == 0
            else sqlalchemy.text("UPDATE model_cost SET cost_per_million_input_tokens = :cost_per_million_input_tokens, cost_per_million_output_tokens = :cost_per_million_output_tokens, cost_per_image = :cost_per_image, cost_per_minute = :cost_per_minute, cost_per_million_characters = :cost_per_million_characters, cost_per_million_reasoning_tokens = :cost_per_million_reasoning_tokens, cost_per_thousand_search_queries = :cost_per_thousand_search_queries WHERE model_name = :model_name")
        )

        connection.execute(
            sql_statement,
            {
                "model_name": model_name,
                "cost_per_million_input_tokens": model_cost["cost_per_million_input_tokens"],
                "cost_per_million_output_tokens": model_cost["cost_per_million_output_tokens"],
                "cost_per_image": model_cost["cost_per_image"],
                "cost_per_minute": model_cost["cost_per_minute"],
                "cost_per_million_characters": model_cost["cost_per_million_characters"],
                "cost_per_million_reasoning_tokens": model_cost["cost_per_million_reasoning_tokens"],
                "cost_per_thousand_search_queries": model_cost["cost_per_thousand_search_queries"],
            },
        )

    for company in companies:
        company_id = company[0]

        # add new models to company
        for model_name, model_data in new_models_list.items():
            existing_model = connection.execute(sqlalchemy.text("SELECT COUNT(*) FROM model WHERE name = :name AND company_id = :company_id"),{"name": model_name, "company_id": company_id}).scalar()
            if existing_model == 0:
                connection.execute(
                    sqlalchemy.text("INSERT INTO model (id, name, meta, params, created_at, updated_at, is_active, company_id) VALUES (:id, :name, :meta, :params, :created_at, :updated_at, :is_active, :company_id)"),
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

    # remove legacy models
    for model_name, model_data in legacy_models_list.items():
        replace_with = model_data["replace_with"]

        # update system models
        if model_name == "GPT 4.1":
            gpt_41_system_model_params = connection.execute(
                sqlalchemy.text("SELECT params FROM model WHERE base_model_id = :name AND company_id = :company_id"),
                {"name": "GPT 4.1", "company_id": "system"},
            ).fetchone()[0]
            gpt_41_system_model_params_json = json.loads(gpt_41_system_model_params) if gpt_41_system_model_params else {}
            gpt_41_system_model_params_json["temperature"] = 1.0

            connection.execute(
                sqlalchemy.text("UPDATE model SET base_model_id = :replace_with, params = :params WHERE base_model_id = :model_name AND company_id = :company_id"),
                {"replace_with": replace_with, "params": json.dumps(gpt_41_system_model_params_json), "model_name": model_name, "company_id": "system"},
            )
        else:
            connection.execute(
                sqlalchemy.text("UPDATE model SET base_model_id = :replace_with WHERE base_model_id = :model_name AND company_id = :company_id"),
                {"replace_with": replace_with, "model_name": model_name, "company_id": "system"},
            )

        # update references and delete legacy models from companies
        for company in companies:
            company_id = company[0]

            legacy_model_id = connection.execute(
                sqlalchemy.text("SELECT id FROM model WHERE name = :name AND company_id = :company_id"),
                {"name": model_name, "company_id": company_id},
            ).scalar()
            replace_model_id = connection.execute(
                sqlalchemy.text("SELECT id FROM model WHERE name = :name AND company_id = :company_id"),
                {"name": replace_with, "company_id": company_id},
            ).scalar()

            if legacy_model_id and replace_model_id:
                connection.execute(
                    sqlalchemy.text("UPDATE model SET base_model_id = :replace_model_id WHERE base_model_id = :legacy_model_id AND company_id = :company_id"),
                    {
                        "replace_model_id": replace_model_id,
                        "legacy_model_id": legacy_model_id,
                        "company_id": company_id,
                    },
                )
                connection.execute(
                    sqlalchemy.text("DELETE FROM model WHERE id = :legacy_model_id AND company_id = :company_id"),
                    {
                        "legacy_model_id": legacy_model_id,
                        "company_id": company_id,
                    },
                )

        connection.execute(
            sqlalchemy.text("DELETE FROM model_cost WHERE model_name = :model_name"),
            {"model_name": model_name},
        )


def downgrade() -> None:
    pass
