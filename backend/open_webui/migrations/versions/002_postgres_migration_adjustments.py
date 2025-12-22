"""Postgres migration adjustments

Revision ID: 002
Revises: 001
Create Date: 2025-12-22 10:07:00.493296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
            ALTER TABLE "auth" ALTER COLUMN "active" TYPE boolean USING "active" = 1;
        """)
    )

    conn.execute(
        sa.text("""
            ALTER TABLE "chat" ALTER COLUMN "archived" TYPE boolean USING "archived" = 1;
        """)
    )

def downgrade() -> None:
    pass
