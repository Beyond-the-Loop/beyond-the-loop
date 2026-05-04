"""Add public_signup_token to company

Revision ID: 038
Revises: 037
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '038'
down_revision: Union[str, None] = '037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE company
                    ADD COLUMN public_signup_token VARCHAR;
                """)
    )

    conn.execute(
        sa.text("""
                CREATE UNIQUE INDEX company_public_signup_token_unique
                    ON company (public_signup_token)
                    WHERE public_signup_token IS NOT NULL;
                """)
    )


def downgrade() -> None:
    pass
