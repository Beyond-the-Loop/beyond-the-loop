"""Remove model columns from company table

Revision ID: 018
Revises: 017
Create Date: 2026-02-12 10:42:38.840349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE company
                    DROP COLUMN default_model;

                ALTER TABLE company
                    DROP COLUMN allowed_models;
                """)
    )


def downgrade() -> None:
    pass
