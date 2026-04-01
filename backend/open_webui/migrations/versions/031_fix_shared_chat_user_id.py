"""Fix shared chat user_id to use 'system' sentinel instead of 'shared-<id>'

Shared chats were created with user_id = 'shared-<chat_id>', which violates the
FK constraint added in migration 026. This migration reassigns those rows to the
'system' sentinel user so that future sharing works correctly.

Revision ID: 031
Revises: 030
Create Date: 2026-04-01 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '031'
down_revision: Union[str, None] = '030'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE chat SET user_id = 'system' WHERE user_id LIKE 'shared-%'"
    ))


def downgrade() -> None:
    return
