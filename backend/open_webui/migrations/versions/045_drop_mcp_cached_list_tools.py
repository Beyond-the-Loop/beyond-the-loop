"""Drop cached_list_tools_item from mcp_server

The cached_list_tools_item path was a pessimisation when combined with
`defer_loading: true` + `tool_search`: injecting the cached tool schemas
into `input` bloated the prompt and made TTFB worse than letting Azure
do a fresh (lazy) discovery. Removing the column and all related code.

Revision ID: 045
Revises: 044
Create Date: 2026-06-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '045'
down_revision: Union[str, None] = '044'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server "
        "DROP COLUMN IF EXISTS cached_list_tools_item;"
    ))


def downgrade() -> None:
    pass
