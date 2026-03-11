"""Remove token cost columns from model_cost table (now sourced from LiteLLM)

Revision ID: 021
Revises: 020
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE model_cost
                    DROP COLUMN IF EXISTS cost_per_million_input_tokens,
                    DROP COLUMN IF EXISTS cost_per_million_output_tokens,
                    DROP COLUMN IF EXISTS cost_per_million_reasoning_tokens;
                """)
    )


def downgrade() -> None:
    pass
