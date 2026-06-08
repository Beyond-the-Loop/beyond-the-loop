"""Add cached_list_tools_item to mcp_server

Stores the most recent `mcp_list_tools` item OpenAI's Responses API returned
for this server, so subsequent chat requests can re-inject it as a past
input item and skip a fresh tools/list roundtrip against the MCP server.

Revision ID: 043
Revises: 042
Create Date: 2026-06-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '043'
down_revision: Union[str, None] = '042'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "ADD COLUMN IF NOT EXISTS cached_list_tools_item JSON;"
    ))


def downgrade() -> None:
    pass
