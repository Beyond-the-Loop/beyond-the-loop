"""Add GPT-5.2 instant/thinking allowed messages to model_cost table

Revision ID: 013
Revises: 012
Create Date: 2026-01-20 14:39:28.174103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                UPDATE
                model_cost
                SET
                allowed_messages_per_three_hours_premium = 50
                WHERE
                model_name
                IN('GPT-5.1 thinking', 'GPT-5.1 instant');
                """)



    )


def downgrade() -> None:
    pass
