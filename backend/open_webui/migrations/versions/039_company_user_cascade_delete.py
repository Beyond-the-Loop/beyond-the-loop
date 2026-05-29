"""Add company -> user cascade delete

Revision ID: 039
Revises: 038
Create Date: 2026-05-29 00:00:00.000000

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
        INSERT INTO company (
            id, name, credit_balance, auto_recharge,
            budget_mail_80_sent, budget_mail_100_sent,
            subscription_not_required
        )
        VALUES
            ('NO_COMPANY', 'No Company', 0, false, false, false, true),
            ('NEW', 'New Company Placeholder', 0, false, false, false, true),
            ('system', 'System', 0, false, false, false, true)
        ON CONFLICT (id) DO NOTHING
    """))

    conn.execute(sa.text("""
        UPDATE "user"
        SET company_id = 'NO_COMPANY'
        WHERE company_id IS NULL
           OR company_id NOT IN (SELECT id FROM company)
    """))

    conn.execute(sa.text("""
        DELETE FROM domain
        WHERE company_id IS NULL
           OR company_id NOT IN (SELECT id FROM company)
    """))

    conn.execute(sa.text("""
        DELETE FROM stripe_payment_history
        WHERE company_id IS NOT NULL
          AND company_id NOT IN (SELECT id FROM company)
    """))

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

    conn.execute(sa.text("""
        ALTER TABLE stripe_payment_history
            DROP CONSTRAINT IF EXISTS stripe_payment_history_company_id_fkey,
            ADD CONSTRAINT stripe_payment_history_company_id_fkey
                FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE CASCADE
    """))


def downgrade() -> None:
    pass
