"""Add oauth_authorize_extra_params column to mcp_server

Some providers (notably Google) require non-standard query parameters on the
authorize URL to issue a refresh_token — `access_type=offline&prompt=consent`.
This column stores those provider-specific params; populated by the catalog
install path, NULL for custom OAuth servers.

Revision ID: 041
Revises: 040
Create Date: 2026-05-19 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '041'
down_revision: Union[str, None] = '040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE mcp_server ADD COLUMN oauth_authorize_extra_params JSON;"
    ))


def downgrade() -> None:
    pass
