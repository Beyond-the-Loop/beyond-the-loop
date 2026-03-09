"""Add smart-router model to all companies

Revision ID: 021
Revises: 020
Create Date: 2026-03-06

"""
import json
import time
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    now = int(time.time())

    companies = conn.execute(sa.text("SELECT id FROM company")).fetchall()

    rows = [
        {
            "id": str(uuid.uuid4()),
            "user_id": None,
            "base_model_id": None,
            "name": "Smart Router",
            "meta": json.dumps({}),
            "params": json.dumps({}),
            "created_at": now,
            "updated_at": now,
            "access_control": None,
            "is_active": True,
            "company_id": company.id,
        }
        for company in companies
    ]

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

    conn.execute(
        sa.text("""
                INSERT
                INTO model_cost(model_name, cost_per_million_input_tokens, cost_per_million_output_tokens,
                                cost_per_image,
                                cost_per_minute, cost_per_million_characters, cost_per_million_reasoning_tokens,
                                cost_per_thousand_search_queries, allowed_messages_per_three_hours_free,
                                allowed_messages_per_three_hours_premium)
                VALUES ('Smart Router', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 300, 300);
                """
            )
    )


def downgrade() -> None:
    pass
