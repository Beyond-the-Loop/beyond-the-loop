"""Add company -> user / domain cascade delete and drop unused stripe_payment_history

Revision ID: 039
Revises: 038
Create Date: 2026-05-29 00:00:00.000000

Adds ON DELETE CASCADE foreign keys from user.company_id and domain.company_id
to company(id) so that deleting a company removes its users (and, via the
existing user cascades, their chats/files/auth/...) and domains automatically.

The 'system' company already exists (created in migration 029); every user is
expected to reference an existing company, so no data backfill is required.

The stripe_payment_history table is no longer used anywhere in the application
and is dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE "user"
            ALTER COLUMN company_id SET NOT NULL,
            DROP CONSTRAINT IF EXISTS user_company_id_fkey,
            ADD CONSTRAINT user_company_id_fkey
                FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE CASCADE
    """))

    conn.execute(sa.text("""
        ALTER TABLE domain
            ALTER COLUMN company_id SET NOT NULL,
            DROP CONSTRAINT IF EXISTS domain_company_id_fkey,
            ADD CONSTRAINT domain_company_id_fkey
                FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE CASCADE
    """))

    # No longer used anywhere in the application.
    conn.execute(sa.text("DROP TABLE IF EXISTS stripe_payment_history"))


def downgrade() -> None:
    pass
