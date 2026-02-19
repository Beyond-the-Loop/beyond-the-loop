"""Add allowed messages for Perplexity models

Revision ID: 016
Revises: 015
Create Date: 2026-02-05 14:22:57.658117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
            UPDATE model_cost
            SET allowed_messages_per_three_hours_premium = 50
            WHERE model_name IN ('Perplexity Sonar Pro');
                
            UPDATE model_cost
            SET allowed_messages_per_three_hours_premium = 5
            WHERE model_name IN ('Perplexity Sonar Deep Research');
                
            UPDATE model_cost
            SET allowed_messages_per_three_hours_premium = 50
            WHERE model_name IN ('Perplexity Sonar Reasoning Pro');
        """)
    )


def downgrade() -> None:
    pass
