"""Remove decommissioned models: repoint assistants to a replacement, then delete

Revision ID: 041
Revises: 040
Create Date: 2026-05-29 00:00:00.000000

Removals:
  - "Grok 4 Fast Reasoning"     -> "Grok 4.1 Fast Non-Reasoning"
  - "Grok 4 Fast Non-Reasoning" -> "Grok 4.1 Fast Non-Reasoning"
  - "GPT o3 Deep Research"      -> "GPT-5.4"
  - "GPT-5.3 Chat"              -> "GPT-5.4"
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '041'
down_revision: Union[str, None] = '040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Map: replacement model name -> list of removed model names to be replaced by it
REPLACEMENTS = {
    "Grok 4.1 Fast Non-Reasoning": ["Grok 4 Fast Reasoning", "Grok 4 Fast Non-Reasoning"],
    "GPT-5.4": ["GPT o3 Deep Research", "GPT-5.3 Chat"],
}


def upgrade() -> None:
    conn = op.get_bind()

    all_removed: list[str] = []

    for replacement, removed in REPLACEMENTS.items():
        all_removed.extend(removed)

        # 1a. System assistants: base_model_id stores the model name directly.
        conn.execute(
            sa.text("""
                UPDATE model
                SET base_model_id = :replacement
                WHERE base_model_id = ANY(:removed)
                  AND user_id = 'system'
            """),
            {"replacement": replacement, "removed": removed},
        )

        # 1b. User assistants: base_model_id stores the UUID of the base model row.
        #     Join to find the replacement model UUID for the same company.
        conn.execute(
            sa.text("""
                UPDATE model AS assistant
                SET base_model_id = replacement.id
                FROM model AS old, model AS replacement
                WHERE assistant.base_model_id = old.id
                  AND old.name = ANY(:removed)
                  AND replacement.company_id = old.company_id
                  AND replacement.name = :replacement
                  AND assistant.user_id != 'system'
            """),
            {"replacement": replacement, "removed": removed},
        )

    # 2. Delete all removed base model rows (now that no assistants reference them).
    conn.execute(
        sa.text("DELETE FROM model WHERE name = ANY(:removed)"),
        {"removed": all_removed},
    )


def downgrade() -> None:
    pass
