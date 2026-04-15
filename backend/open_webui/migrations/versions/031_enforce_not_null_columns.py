"""Enforce NOT NULL on all columns that are semantically required

Revision ID: 031
Revises: 030
Create Date: 2026-04-01 00:00:00.000000

All Column() definitions without explicit nullable=False default to nullable=True
in SQLAlchemy, which means PG also accepts NULLs.  This migration fills any
existing NULLs with sensible defaults and then sets NOT NULL on every column
that must always have a value.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '031'
down_revision: Union[str, None] = '030'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _run(conn, sql: str, **params):
    conn.execute(sa.text(sql), params)


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ user
    _run(conn, 'UPDATE "user" SET first_name       = \'\' WHERE first_name       IS NULL')
    _run(conn, 'UPDATE "user" SET last_name        = \'\' WHERE last_name        IS NULL')
    _run(conn, 'UPDATE "user" SET email            = \'\' WHERE email            IS NULL')
    _run(conn, 'UPDATE "user" SET role             = \'user\' WHERE role         IS NULL')
    _run(conn, 'UPDATE "user" SET profile_image_url= \'\' WHERE profile_image_url IS NULL')
    _run(conn, 'UPDATE "user" SET last_active_at   = 0   WHERE last_active_at   IS NULL')
    _run(conn, 'UPDATE "user" SET updated_at       = 0   WHERE updated_at       IS NULL')
    _run(conn, 'UPDATE "user" SET created_at       = 0   WHERE created_at       IS NULL')
    for col in ('first_name', 'last_name', 'email', 'role', 'profile_image_url',
                'last_active_at', 'updated_at', 'created_at'):
        _run(conn, f'ALTER TABLE "user" ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- company
    _run(conn, 'UPDATE company SET credit_balance      = 0     WHERE credit_balance      IS NULL')
    _run(conn, 'UPDATE company SET auto_recharge       = false WHERE auto_recharge       IS NULL')
    _run(conn, 'UPDATE company SET budget_mail_80_sent  = false WHERE budget_mail_80_sent  IS NULL')
    _run(conn, 'UPDATE company SET budget_mail_100_sent = false WHERE budget_mail_100_sent IS NULL')
    for col in ('credit_balance', 'auto_recharge', 'budget_mail_80_sent', 'budget_mail_100_sent'):
        _run(conn, f'ALTER TABLE company ALTER COLUMN {col} SET NOT NULL')

    # ----------------------------------------------------------------- model
    _run(conn, "UPDATE model SET name       = ''       WHERE name       IS NULL")
    _run(conn, "UPDATE model SET user_id    = 'system' WHERE user_id    IS NULL")
    _run(conn, 'UPDATE model SET is_active  = true     WHERE is_active  IS NULL')
    _run(conn, 'UPDATE model SET updated_at = 0        WHERE updated_at IS NULL')
    _run(conn, 'UPDATE model SET created_at = 0        WHERE created_at IS NULL')
    for col in ('name', 'user_id', 'is_active', 'updated_at', 'created_at'):
        _run(conn, f'ALTER TABLE model ALTER COLUMN {col} SET NOT NULL')

    # ---------------------------------------------------------------- prompt
    _run(conn, "UPDATE prompt SET title     = '' WHERE title     IS NULL")
    _run(conn, 'UPDATE prompt SET timestamp = 0  WHERE timestamp IS NULL')
    _run(conn, 'UPDATE prompt SET prebuilt  = false WHERE prebuilt IS NULL')
    for col in ('title', 'timestamp', 'prebuilt'):
        _run(conn, f'ALTER TABLE prompt ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- knowledge
    _run(conn, "UPDATE knowledge SET user_id    = 'system' WHERE user_id    IS NULL")
    _run(conn, "UPDATE knowledge SET name       = ''       WHERE name       IS NULL")
    _run(conn, 'UPDATE knowledge SET created_at = 0        WHERE created_at IS NULL')
    _run(conn, 'UPDATE knowledge SET updated_at = 0        WHERE updated_at IS NULL')
    for col in ('user_id', 'name', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE knowledge ALTER COLUMN {col} SET NOT NULL')

    # ----------------------------------------------------------------- group
    _run(conn, 'UPDATE "group" SET name       = \'\' WHERE name       IS NULL')
    _run(conn, 'UPDATE "group" SET created_at = 0   WHERE created_at IS NULL')
    _run(conn, 'UPDATE "group" SET updated_at = 0   WHERE updated_at IS NULL')
    for col in ('name', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE "group" ALTER COLUMN {col} SET NOT NULL')

    # ------------------------------------------------------------------ file
    _run(conn, "UPDATE file SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE file SET filename   = '' WHERE filename   IS NULL")
    _run(conn, 'UPDATE file SET created_at = 0  WHERE created_at IS NULL')
    _run(conn, 'UPDATE file SET updated_at = 0  WHERE updated_at IS NULL')
    for col in ('user_id', 'filename', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE file ALTER COLUMN {col} SET NOT NULL')

    # ------------------------------------------------------------------ auth
    _run(conn, "UPDATE auth SET email  = '' WHERE email  IS NULL")
    _run(conn, 'UPDATE auth SET active = false WHERE active IS NULL')
    for col in ('email', 'active'):
        _run(conn, f'ALTER TABLE auth ALTER COLUMN {col} SET NOT NULL')

    # ------------------------------------------------------------------ chat
    _run(conn, "UPDATE chat SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE chat SET title      = '' WHERE title      IS NULL")
    _run(conn, "UPDATE chat SET chat       = '{}' WHERE chat     IS NULL")
    _run(conn, 'UPDATE chat SET created_at = 0   WHERE created_at IS NULL')
    _run(conn, 'UPDATE chat SET updated_at = 0   WHERE updated_at IS NULL')
    _run(conn, 'UPDATE chat SET archived   = false WHERE archived  IS NULL')
    _run(conn, 'UPDATE chat SET pinned     = false WHERE pinned    IS NULL')
    for col in ('user_id', 'title', 'chat', 'created_at', 'updated_at', 'archived', 'pinned'):
        _run(conn, f'ALTER TABLE chat ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- channel
    _run(conn, "UPDATE channel SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE channel SET name       = '' WHERE name       IS NULL")
    _run(conn, 'UPDATE channel SET created_at = 0  WHERE created_at IS NULL')
    _run(conn, 'UPDATE channel SET updated_at = 0  WHERE updated_at IS NULL')
    for col in ('user_id', 'name', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE channel ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- folder
    _run(conn, "UPDATE folder SET user_id     = '' WHERE user_id     IS NULL")
    _run(conn, "UPDATE folder SET name        = '' WHERE name        IS NULL")
    _run(conn, 'UPDATE folder SET is_expanded = false WHERE is_expanded IS NULL')
    _run(conn, 'UPDATE folder SET created_at  = 0   WHERE created_at  IS NULL')
    _run(conn, 'UPDATE folder SET updated_at  = 0   WHERE updated_at  IS NULL')
    for col in ('user_id', 'name', 'is_expanded', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE folder ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- memory
    _run(conn, "UPDATE memory SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE memory SET content    = '' WHERE content    IS NULL")
    _run(conn, 'UPDATE memory SET updated_at = 0  WHERE updated_at IS NULL')
    _run(conn, 'UPDATE memory SET created_at = 0  WHERE created_at IS NULL')
    for col in ('user_id', 'content', 'updated_at', 'created_at'):
        _run(conn, f'ALTER TABLE memory ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- message
    _run(conn, "UPDATE message SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE message SET channel_id = '' WHERE channel_id IS NULL")
    _run(conn, "UPDATE message SET content    = '' WHERE content    IS NULL")
    _run(conn, 'UPDATE message SET created_at = 0  WHERE created_at IS NULL')
    _run(conn, 'UPDATE message SET updated_at = 0  WHERE updated_at IS NULL')
    for col in ('user_id', 'channel_id', 'content', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE message ALTER COLUMN {col} SET NOT NULL')

    # -------------------------------------------------------- message_reaction
    _run(conn, "UPDATE message_reaction SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, "UPDATE message_reaction SET message_id = '' WHERE message_id IS NULL")
    _run(conn, "UPDATE message_reaction SET name       = '' WHERE name       IS NULL")
    _run(conn, 'UPDATE message_reaction SET created_at = 0  WHERE created_at IS NULL')
    for col in ('user_id', 'message_id', 'name', 'created_at'):
        _run(conn, f'ALTER TABLE message_reaction ALTER COLUMN {col} SET NOT NULL')

    # --------------------------------------------------------------- feedback
    _run(conn, "UPDATE feedback SET user_id    = '' WHERE user_id    IS NULL")
    _run(conn, 'UPDATE feedback SET version    = 0  WHERE version    IS NULL')
    _run(conn, "UPDATE feedback SET type       = '' WHERE type       IS NULL")
    _run(conn, 'UPDATE feedback SET created_at = 0  WHERE created_at IS NULL')
    _run(conn, 'UPDATE feedback SET updated_at = 0  WHERE updated_at IS NULL')
    for col in ('user_id', 'version', 'type', 'created_at', 'updated_at'):
        _run(conn, f'ALTER TABLE feedback ALTER COLUMN {col} SET NOT NULL')

    # ------------------------------------------------------------------- tag
    _run(conn, "UPDATE tag SET name = '' WHERE name IS NULL")
    _run(conn, 'ALTER TABLE tag ALTER COLUMN name SET NOT NULL')

    # --------------------------------------------------------------- completion
    _run(conn, "UPDATE completion SET model              = '' WHERE model              IS NULL")
    _run(conn, 'UPDATE completion SET credits_used       = 0  WHERE credits_used       IS NULL')
    _run(conn, 'UPDATE completion SET created_at         = 0  WHERE created_at         IS NULL')
    _run(conn, 'UPDATE completion SET from_agent         = false WHERE from_agent       IS NULL')
    _run(conn, 'UPDATE completion SET is_image_generation= false WHERE is_image_generation IS NULL')
    for col in ('model', 'credits_used', 'created_at', 'from_agent', 'is_image_generation'):
        _run(conn, f'ALTER TABLE completion ALTER COLUMN {col} SET NOT NULL')


def downgrade() -> None:
    return
