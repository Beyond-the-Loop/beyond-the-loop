"""add_domain_table

Revision ID: e956533c9867
Revises: fbde9eebf688
Create Date: 2025-07-25 21:30:45.890596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'e956533c9867'
down_revision: Union[str, None] = 'fbde9eebf688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("company_id", sa.Text(), nullable=False),
        sa.Column("domain_fqdn", sa.Text(), nullable=False, unique=True),
        sa.Column("dns_approval_record", sa.Text(), nullable=False),
        sa.Column("ownership_approved", sa.Boolean(), default=False, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("domain_fqdn"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="CASCADE")
    )


def downgrade() -> None:
    op.drop_table("domain")
