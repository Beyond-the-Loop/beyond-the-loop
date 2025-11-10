"""Drop function and tool tables

Revision ID: 0f2a3b4c5d6e
Revises: 5eeb9eee6f05
Create Date: 2025-11-06 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db

# revision identifiers, used by Alembic.
revision: str = "0f2a3b4c5d6e"
down_revision: Union[str, None] = "5eeb9eee6f05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop the tables if they exist
    existing_tables = set(inspector.get_table_names())

    if "function" in existing_tables:
        op.drop_table("function")

    if "tool" in existing_tables:
        op.drop_table("tool")


def downgrade() -> None:
    # Intentionally left blank as re-creating removed tables is not required for this change.
    pass
