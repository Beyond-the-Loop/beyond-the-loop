"""Add next_credit_recharge_check column

Revision ID: f26c72213149
Revises: dfff99fbe06b
Create Date: 2025-12-08 14:40:48.899856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'f26c72213149'
down_revision: Union[str, None] = 'dfff99fbe06b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('company', sa.Column('next_credit_charge_check', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('prompt', 'next_credit_charge_check')

