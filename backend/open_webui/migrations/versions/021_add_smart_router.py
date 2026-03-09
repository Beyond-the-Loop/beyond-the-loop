"""Add smart-router model to all companies

Revision ID: 021
Revises: 020
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import time
import uuid
import json


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    now = int(time.time())

    companies = conn.execute(sa.text("SELECT id FROM company")).fetchall()

    meta = json.dumps({
        "description": "Wählt automatisch das beste Modell basierend auf der Komplexität deiner Anfrage.",
        "tags": [{"name": "auto"}],
        "capabilities": {
            "vision": False,
            "usage": True,
            "citations": False,
        },
    })

    rows = [
        {
            "id": str(uuid.uuid4()),
            "user_id": None,
            "base_model_id": None,
            "name": "smart-router",
            "meta": meta,
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


def downgrade() -> None:
    pass
