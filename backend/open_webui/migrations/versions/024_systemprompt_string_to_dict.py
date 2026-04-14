"""Migrate user.settings ui.system from string to dict

Revision ID: 024
Revises: 023
Create Date: 2026-03-24 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '024'
down_revision: Union[str, None] = '023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE "user"
            SET settings = jsonb_set(
                settings::jsonb,
                '{ui,system}',
                jsonb_build_object(
                    'promptStyle', 'default',
                    'customInstruction', settings::jsonb #>> '{ui,system}'
                )
            )::text
            WHERE settings IS NOT NULL
              AND jsonb_typeof(settings::jsonb #> '{ui,system}') = 'string';
        """)
    )


def downgrade() -> None:
    pass