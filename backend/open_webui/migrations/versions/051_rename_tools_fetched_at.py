"""Rename mcp_server.tools_fetched_at -> last_refreshed_at

The timestamp is no longer purely about the tools list — the unified
connector refresh button also touches it whenever any side-effect
successfully talks to the MCP server. Renaming so the label matches
the meaning surfaced in the UI ("Zuletzt aktualisiert" on the whole
connector, not on any one sub-section).

Revision ID: 051
Revises: 050
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '051'
down_revision: Union[str, None] = '050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "RENAME COLUMN tools_fetched_at TO last_refreshed_at;"
    ))


def downgrade() -> None:
    raise NotImplementedError(
        "Migration 051 is forward-only. To roll back, rename the column "
        "back to tools_fetched_at and adjust any code that reads it."
    )
