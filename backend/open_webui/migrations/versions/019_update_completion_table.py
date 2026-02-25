"""Update completion table

Revision ID: 019
Revises: 018
Create Date: 2026-02-08 19:24:46.263508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE completion
                    DROP COLUMN time_saved_in_seconds;
                
                ALTER TABLE completion
                    DROP COLUMN chat_id;

                ALTER TABLE completion
                    ADD COLUMN assistant text;
                    
                ALTER TABLE completion
                    ADD COLUMN from_agent boolean;
                """)
    )


def downgrade() -> None:
    pass
