"""Remove GPT-5.1 Chat model: repoint assistants to GPT-5.1, then delete

Revision ID: 025
Revises: 024
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '025'
down_revision: Union[str, None] = '024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1a. System assistants: base_model_id stores the model name directly.
    conn.execute(
        sa.text("""
            UPDATE model
            SET base_model_id = 'Gemini 3.1 Flash-Lite'
            WHERE base_model_id = 'GPT-5.1 Chat'
              AND user_id = 'system'
        """)
    )

    # 1b. User assistants: base_model_id stores the UUID of the base model row.
    #     Join to find the Gemini 3.1 Flash-Lite model UUID for the same company.
    conn.execute(
        sa.text("""
            UPDATE model AS assistant
            SET base_model_id = gpt51.id
            FROM model AS chat, model AS gpt51
            WHERE assistant.base_model_id = chat.id
              AND chat.name = 'GPT-5.1 Chat'
              AND gpt51.company_id = chat.company_id
              AND gpt51.name = 'Gemini 3.1 Flash-Lite'
              AND assistant.user_id != 'system'
        """)
    )

    # 2. Delete the GPT-5.1 Chat base models (now that no assistants reference them).
    conn.execute(
        sa.text("DELETE FROM model WHERE name = 'GPT-5.1 Chat'"),
    )


def downgrade() -> None:
    pass
