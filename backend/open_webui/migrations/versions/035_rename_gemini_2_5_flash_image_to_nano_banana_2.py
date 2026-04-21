"""Rename Gemini 2.5 Flash Image to Nano Banana 2

Revision ID: 035
Revises: 034
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '035'
down_revision: Union[str, None] = '034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_NAME = "Gemini 2.5 Flash Image"
NEW_NAME = "Nano Banana 2"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE model SET name = :new_name WHERE name = :old_name"),
        {"new_name": NEW_NAME, "old_name": OLD_NAME},
    )


def downgrade() -> None:
    pass
