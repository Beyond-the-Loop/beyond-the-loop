"""Drop mcp_server.available_scopes

Under Option X (auto-discover from RFC 9728 PRM at install and refresh),
`available_scopes` and `oauth_scope` both derive from the same PRM
`scopes_supported` array. `available_scopes` was intended as an admin-visible
"what could the server do" list, but since we already request everything the
server offers, it holds no unique signal beyond `oauth_scope`. Dropped.

Revision ID: 050
Revises: 049
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '050'
down_revision: Union[str, None] = '049'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server DROP COLUMN IF EXISTS available_scopes;"
    ))


def downgrade() -> None:
    raise NotImplementedError(
        "Migration 050 is forward-only. To roll back, reinstate the "
        "mcp_server.available_scopes JSON column and repopulate it from "
        "PRM on next GET /{server_id}."
    )
