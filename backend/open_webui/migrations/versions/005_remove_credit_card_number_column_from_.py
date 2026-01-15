"""Remove credit_card_number column from company table

Revision ID: 005
Revises: 004
Create Date: 2026-01-08 16:20:50.644236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE company
                DROP COLUMN credit_card_number;
                """)
    )


def downgrade() -> None:
    pass
