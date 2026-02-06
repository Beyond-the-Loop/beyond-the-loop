"""Add alerts table

Revision ID: 015
Revises: 014
Create Date: 2026-02-02 08:44:25.386602

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'alert_type'
            ) THEN
                CREATE TYPE alert_type AS ENUM (
                    'info',
                    'warning',
                    'success'
                );
            END IF;
        END
        $$;
        """)
    )

    conn.execute(
        sa.text("""
                CREATE TABLE alert
                (
                    id      BIGSERIAL PRIMARY KEY,
                    title   VARCHAR(255) NOT NULL,
                    message TEXT         NOT NULL,
                    type    alert_type
                );
                """)
    )


def downgrade() -> None:
    pass
