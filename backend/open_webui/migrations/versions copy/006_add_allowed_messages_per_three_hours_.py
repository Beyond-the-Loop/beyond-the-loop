"""Add allowed_messages_per_three_hours column to model_cost

Revision ID: 006
Revises: 005
Create Date: 2026-01-12 16:47:40.450401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE model_cost
                    ADD COLUMN allowed_messages_per_three_hours_free INTEGER;
                    
                ALTER TABLE model_cost
                    ADD COLUMN allowed_messages_per_three_hours_premium INTEGER;
                """)
    )


def downgrade() -> None:
    pass
