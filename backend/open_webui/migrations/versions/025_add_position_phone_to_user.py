"""Add position and phone columns to user table

<<<<<<<< HEAD:backend/open_webui/migrations/versions/025_add_position_phone_to_user.py
Revision ID: 025
Revises: 024
========
Revision ID: 026
Revises: 025
>>>>>>>> feature/signup_flow:backend/open_webui/migrations/versions/026_add_position_phone_to_user.py
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
<<<<<<<< HEAD:backend/open_webui/migrations/versions/025_add_position_phone_to_user.py
revision: str = '025'
down_revision: Union[str, None] = '024'
========
revision: str = '026'
down_revision: Union[str, None] = '025'
>>>>>>>> feature/signup_flow:backend/open_webui/migrations/versions/026_add_position_phone_to_user.py
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE "user"
                    ADD COLUMN IF NOT EXISTS position VARCHAR,
                    ADD COLUMN IF NOT EXISTS phone VARCHAR;
                """)
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
                ALTER TABLE "user"
                    DROP COLUMN IF EXISTS position,
                    DROP COLUMN IF EXISTS phone;
                """)
    )
