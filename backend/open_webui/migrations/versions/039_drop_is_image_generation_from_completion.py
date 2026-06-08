"""Drop is_image_generation from completion table

Revision ID: 042
Revises: 041
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '042'
down_revision: Union[str, None] = '041'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE completion
                    DROP COLUMN IF EXISTS is_image_generation;
                """)
    )


def downgrade() -> None:
    pass
