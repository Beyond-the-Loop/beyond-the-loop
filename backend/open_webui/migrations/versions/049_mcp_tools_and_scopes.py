"""Drop tool_filter, add tools/tools_fetched_at/available_scopes on mcp_server

Unifies "known tools" and "which tools are enabled" into a single JSON
column, and caches the RFC 9728 PRM `scopes_supported` snapshot for
mismatch detection in the admin UI.

Revision ID: 049
Revises: 048
Create Date: 2026-07-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '049'
down_revision: Union[str, None] = '048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "DROP COLUMN IF EXISTS tool_filter;"
    ))
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "ADD COLUMN IF NOT EXISTS tools JSON;"
    ))
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "ADD COLUMN IF NOT EXISTS tools_fetched_at TIMESTAMP WITH TIME ZONE;"
    ))
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "ADD COLUMN IF NOT EXISTS available_scopes JSON;"
    ))


def downgrade() -> None:
    raise NotImplementedError(
        "Migration 049 is forward-only. To roll back you must "
        "restore from a pre-049 backup or manually reinstate "
        "the mcp_server.tool_filter column and drop tools/tools_fetched_at/available_scopes."
    )
