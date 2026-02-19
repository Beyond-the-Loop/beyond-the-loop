"""Add new models to existing companies

Revision ID: 008
Revises: 007
Create Date: 2026-01-14 15:30:03.881920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import time
import uuid
import json


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    MODEL_NAMES = [
        "Grok 4 fast (thinking)",
        "Grok 4 fast (instant)",
        "GPT OSS 120b",
        "Mistral Large 3",
        "DeepSeek-V3.2",
        "DeepSeek R1",
        "GPT-5.1 Codex",
        "GPT-5.2",
        "GPT o3 Deep Research",
    ]

    conn = op.get_bind()
    now = int(time.time())

    # Fetch all companies
    companies = conn.execute(
        sa.text("SELECT id FROM company")
    ).fetchall()

    rows = []

    for company in companies:
        for model_name in MODEL_NAMES:
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
                    "is_active": True,
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
