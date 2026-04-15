"""Update models for new litellm config: rename changed models, add new models, delete Grok 4

Revision ID: 023
Revises: 022
Create Date: 2026-03-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import time
import uuid
import json


# revision identifiers, used by Alembic.
revision: str = '023'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RENAMES = [
    ("GPT-5.1 instant", "GPT-5.1 Chat"),
    ("GPT-5.1 thinking", "GPT-5.1"),
    ("Grok 4 fast (thinking)", "Grok 4 Fast Reasoning"),
    ("Grok 4 fast (instant)", "Grok 4 Fast Non-Reasoning"),
    ("GPT-5.1 Codex", "GPT-5.3 Codex"),
    ("Google 2.5 Flash", "Gemini 2.5 Flash"),
    ("Google 2.5 Pro", "Gemini 2.5 Pro"),
]

NEW_MODELS = [
    "Claude Sonnet 4.6",
    "Claude Opus 4.6",
    "Gemini 3 Flash",
    "Gemini 3 Pro",
    "Gemini 3.1 Flash-Lite",
    "Grok 4.1 Fast Reasoning",
    "Grok 4.1 Fast Non-Reasoning",
    "DeepSeek R1-0528",
    "GPT-5.4 Pro",
    "GPT-5.4",
    "GPT-5.3 Chat",
    "Gemini 3.1 Pro",
    "Perplexity Sonar",
    "Mistral Large 3"
]

DELETED_MODELS = [
    "Grok 4",
    "Mistral Large 2",
]


def upgrade() -> None:
    conn = op.get_bind()
    now = int(time.time())

    # 1. Rename changed models (model.name, model.base_model_id for assistants, completion.model)
    for old_name, new_name in RENAMES:
        conn.execute(
            sa.text("UPDATE model SET name = :new_name WHERE name = :old_name"),
            {"old_name": old_name, "new_name": new_name},
        )
        conn.execute(
            sa.text("UPDATE model SET base_model_id = :new_name WHERE base_model_id = :old_name"),
            {"old_name": old_name, "new_name": new_name},
        )
        conn.execute(
            sa.text("UPDATE completion SET model = :new_name WHERE model = :old_name"),
            {"old_name": old_name, "new_name": new_name},
        )

    # 2. Delete removed models
    for model_name in DELETED_MODELS:
        conn.execute(
            sa.text("DELETE FROM model WHERE name = :name"),
            {"name": model_name},
        )

    # 3. Add new models for each company (skip if already exists)
    companies = conn.execute(sa.text("SELECT id FROM company")).fetchall()

    rows = []
    for company in companies:
        existing = conn.execute(
            sa.text("SELECT name FROM model WHERE company_id = :company_id AND name = ANY(:names)"),
            {"company_id": company.id, "names": NEW_MODELS},
        ).fetchall()
        existing_names = {row.name for row in existing}

        for model_name in NEW_MODELS:
            if model_name not in existing_names:
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": None,
                        "base_model_id": None,
                        "name": model_name,
                        "meta": json.dumps({}),
                        "params": json.dumps({}),
                        "created_at": now,
                        "updated_at": now,
                        "access_control": None,
                        "is_active": False if model_name == "Claude Opus 4.6" else True,
                        "company_id": company.id,
                    }
                )

    if rows:
        op.bulk_insert(
            sa.table(
                "model",
                sa.column("id", sa.String),
                sa.column("user_id", sa.String),
                sa.column("base_model_id", sa.String),
                sa.column("name", sa.String),
                sa.column("meta", sa.String),
                sa.column("params", sa.String),
                sa.column("created_at", sa.BigInteger),
                sa.column("updated_at", sa.BigInteger),
                sa.column("access_control", sa.JSON),
                sa.column("is_active", sa.Boolean),
                sa.column("company_id", sa.String),
            ),
            rows,
        )


def downgrade() -> None:
    pass
