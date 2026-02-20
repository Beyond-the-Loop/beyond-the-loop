"""Add Nano Banana to model_cost table

Revision ID: 017
Revises: 016
Create Date: 2026-02-17 11:41:14.406724
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                UPDATE model_cost
                SET model_name = 'Nano Banana'
                WHERE model_name = 'flux-kontext-max';
                """)
    )


def downgrade() -> None:
    pass
