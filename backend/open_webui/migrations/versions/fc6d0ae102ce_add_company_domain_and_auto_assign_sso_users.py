"""Add subscription_not_required column to company table

Revision ID: fc6d0ae102ce
Revises: fbde9eebf688
Create Date: 2025-06-03 20:49:37.175519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'fc6d0ae102ce'
down_revision: Union[str, None] = 'fbde9eebf688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('company', sa.Column('domain', sa.String(), nullable=True))
    op.add_column('company', sa.Column('auto_assign_sso_users', sa.Boolean(), default=False))


def downgrade() -> None:
    op.drop_column('company', 'domain')
    op.drop_column('company', 'auto_assign_sso_users')
