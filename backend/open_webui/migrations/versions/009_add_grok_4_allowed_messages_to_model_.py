"""Add Grok 4 allowed_messages to model_cost Table

Revision ID: 009
Revises: 008
Create Date: 2026-01-15 10:28:28.845722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                UPDATE model_cost SET allowed_messages_per_three_hours_premium = 50 WHERE model_name = 'Grok 4';
                """)
    )

def downgrade() -> None:
    pass
