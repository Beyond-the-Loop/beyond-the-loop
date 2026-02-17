"""Add new models to cost table

Revision ID: 010
Revises: 009
Create Date: 2026-01-16 13:39:22.645148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
            UPDATE model_cost SET allowed_messages_per_three_hours_free = 300, allowed_messages_per_three_hours_premium = 300 WHERE model_name IN ('Google 2.5 Flash');
            """
        )
    )

def downgrade() -> None:
    pass