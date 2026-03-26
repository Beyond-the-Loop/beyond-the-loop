"""Add position and phone columns to user table

Revision ID: 025
Revises: 024
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '025'
down_revision: Union[str, None] = '024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE "user"
                    ADD COLUMN IF NOT EXISTS position VARCHAR,
                    ADD COLUMN IF NOT EXISTS phone VARCHAR;
                """)
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE "user"
                    DROP COLUMN IF EXISTS position,
                    DROP COLUMN IF EXISTS phone;
                """)
    )
