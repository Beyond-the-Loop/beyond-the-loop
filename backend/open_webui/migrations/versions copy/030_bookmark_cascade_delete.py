"""Add ON DELETE CASCADE FK constraints to bookmark join tables

Revision ID: 030
Revises: 029
Create Date: 2026-04-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '030'
down_revision: Union[str, None] = '029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables created in 001_init_db without FK constraints — fix them here.
BOOKMARK_CONSTRAINTS = [
    # (table, constraint_name, fk_column, referenced_table_column)
    ("user_model_bookmark",  "user_model_bookmark_user_id_fkey",  "user_id",  '"user"(id)'),
    ("user_model_bookmark",  "user_model_bookmark_model_id_fkey", "model_id", '"model"(id)'),
    ("user_prompt_bookmark", "user_prompt_bookmark_user_id_fkey", "user_id",  '"user"(id)'),
    ("user_prompt_bookmark", "user_prompt_bookmark_prompt_command_fkey", "prompt_command", '"prompt"(command)'),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Delete orphaned rows before adding FK constraints
    conn.execute(sa.text(
        'DELETE FROM user_model_bookmark '
        'WHERE user_id NOT IN (SELECT id FROM "user") OR model_id NOT IN (SELECT id FROM model)'
    ))
    conn.execute(sa.text(
        'DELETE FROM user_prompt_bookmark '
        'WHERE user_id NOT IN (SELECT id FROM "user") OR prompt_command NOT IN (SELECT command FROM prompt)'
    ))

    for table, constraint, column, ref in BOOKMARK_CONSTRAINTS:
        conn.execute(sa.text(
            f'ALTER TABLE {table} '
            f'DROP CONSTRAINT IF EXISTS {constraint}, '
            f'ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) REFERENCES {ref} ON DELETE CASCADE'
        ))


def downgrade() -> None:
    return
