"""Add June 2027 models to all companies

Revision ID: 040
Revises: 039
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import time
import uuid
import json


# revision identifiers, used by Alembic.
revision: str = '040'
down_revision: Union[str, None] = '039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_MODELS = [
    "Claude Opus 4.8",
    "Gemini 3.5 Flash",
    "GPT-5.5"
]


def upgrade() -> None:
    conn = op.get_bind()
    now = int(time.time())

    companies = conn.execute(sa.text("SELECT id FROM company WHERE id != 'system'")).fetchall()

    rows = []
    for company in companies:
        for model_name in NEW_MODELS:
            existing = conn.execute(
                sa.text("SELECT name FROM model WHERE company_id = :company_id AND name = :name"),
                {"company_id": company.id, "name": model_name},
            ).fetchone()

            if not existing:
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": "system",
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


def downgrade():
    return
