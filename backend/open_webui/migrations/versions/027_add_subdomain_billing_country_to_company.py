"""Add subdomain and billing_country to company, remove size/industry/team_function

Revision ID: 027
Revises: 026
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '027'
down_revision: Union[str, None] = '026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE company
                    ADD COLUMN subdomain VARCHAR,
                    ADD COLUMN billing_country VARCHAR;
                """)
    )

    conn.execute(
        sa.text("""
                ALTER TABLE company
                    DROP COLUMN IF EXISTS size,
                    DROP COLUMN IF EXISTS industry,
                    DROP COLUMN IF EXISTS team_function;
                """)
    )


def downgrade() -> None:
    pass
