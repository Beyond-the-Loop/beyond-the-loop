"""Add ON DELETE CASCADE FK from model.user_id to user

Revision ID: 030
Revises: 029
Create Date: 2026-04-01 00:00:00.000000

Why: model.user_id was a plain TEXT column with no referential integrity.
Deleting a user left orphaned model rows.  Adding the FK ensures that:
  - transferred models survive (user_id was updated before the user row is deleted)
  - non-transferred models are automatically removed together with the user
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '030'
down_revision: Union[str, None] = '029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Remove orphaned model rows whose user_id no longer exists in the user table.
    # ('system' is a valid sentinel user inserted in migration 026.)
    conn.execute(sa.text(
        'DELETE FROM model WHERE user_id NOT IN (SELECT id FROM "user")'
    ))

    conn.execute(sa.text(
        'ALTER TABLE model '
        'DROP CONSTRAINT IF EXISTS model_user_id_fkey, '
        'ADD CONSTRAINT model_user_id_fkey '
        'FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE'
    ))


def downgrade() -> None:
    return
