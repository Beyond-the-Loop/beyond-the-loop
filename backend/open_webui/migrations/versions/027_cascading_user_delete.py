"""Add sentinel 'system' user and ON DELETE CASCADE foreign keys

Revision ID: 027
Revises: 026
Create Date: 2026-03-24 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import open_webui.internal.db

# revision identifiers, used by Alembic.
revision: str = '027'
down_revision: Union[str, None] = '026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CASCADE_CONSTRAINTS = [
    # (table, constraint_name, fk_column, referenced)
    ("auth",             "auth_id_fkey",                  "id",      '"user"(id)'),
    ("chat",             "chat_user_id_fkey",              "user_id", '"user"(id)'),
    ("model",            "model_user_id_fkey",             "user_id", '"user"(id)'),
    ("prompt",           "prompt_user_id_fkey",            "user_id", '"user"(id)'),
    ("file",             "file_user_id_fkey",              "user_id", '"user"(id)'),
    ("knowledge",        "knowledge_user_id_fkey",         "user_id", '"user"(id)'),
    ("folder",           "folder_user_id_fkey",            "user_id", '"user"(id)'),
    ("memory",           "memory_user_id_fkey",            "user_id", '"user"(id)'),
    ("feedback",         "feedback_user_id_fkey",          "user_id", '"user"(id)'),
    ("message",          "message_user_id_fkey",           "user_id", '"user"(id)'),
    ("message_reaction", "message_reaction_user_id_fkey",  "user_id", '"user"(id)'),
    ("channel",          "channel_user_id_fkey",           "user_id", '"user"(id)'),
    ("tag",              "tag_user_id_fkey",               "user_id", '"user"(id)'),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Create sentinel 'system' user so that model/prompt rows with
    # user_id='system' satisfy the FK constraint.
    conn.execute(sa.text("""
        INSERT INTO "user" (id, role, first_name, last_name, email,
                            profile_image_url, company_id,
                            created_at, updated_at, last_active_at)
        VALUES ('system', 'system', 'System', '', 'system@system.internal', '',
                'system', 0, 0, 0)
        ON CONFLICT (id) DO NOTHING
    """))

    for table, constraint, column, ref in CASCADE_CONSTRAINTS:
        if table == 'auth':
            conn.execute(sa.text(
            f'DELETE FROM "{table}" '
            f'WHERE id NOT IN (SELECT id FROM "user") AND id != \'system\' AND id IS NOT NULL'
        ))
        else:
            conn.execute(sa.text(
                f'DELETE FROM "{table}" '
                f'WHERE user_id NOT IN (SELECT id FROM "user") AND user_id != \'system\' AND user_id IS NOT NULL'
            ))
        conn.execute(sa.text(
            f'DELETE FROM "{table}" '
            f'WHERE user_id NOT IN (SELECT id FROM "user") AND user_id != \'system\' AND user_id IS NOT NULL'
        ))
        conn.execute(sa.text(
            f'ALTER TABLE "{table}" '
            f'DROP CONSTRAINT IF EXISTS {constraint}, '
            f'ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) REFERENCES {ref} ON DELETE CASCADE'
        ))


def downgrade() -> None:
    conn = op.get_bind()

    for table, constraint, _, _ in CASCADE_CONSTRAINTS:
        conn.execute(sa.text(
            f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS {constraint}'
        ))

    conn.execute(sa.text("""
        DELETE FROM "user" WHERE id = 'system'
    """))
