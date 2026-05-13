"""MCP server: template installation, OAuth revocation, DCR management

Combines three incremental MCP changes into a single migration:

  1. template_slug column + partial unique index — marks rows installed from
     the Library catalog and enforces one row per (user, template_slug) so
     reconnecting a Library connector reuses the cached client_id/secret
     instead of re-running discovery + DCR.

  2. oauth_revocation_endpoint column — cached from the provider's RFC 8414
     discovery doc so /oauth/disconnect can revoke tokens at the provider
     (RFC 7009) instead of just clearing locally. Backfilled from the
     already-stored oauth_discovery_metadata.

  3. oauth_registration_client_uri + oauth_registration_access_token_encrypted
     columns — RFC 7592 DCR management URL + bearer. Let /oauth/disconnect
     DELETE the registered client at the provider so it disappears from the
     user's connected-apps list, not just from our DB.

All operations use `IF NOT EXISTS` so re-running against a partially-migrated
DB (e.g. during development) is safe.

Revision ID: 042
Revises: 041
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '042'
down_revision: Union[str, None] = '041'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE mcp_server
            ADD COLUMN IF NOT EXISTS template_slug VARCHAR,
            ADD COLUMN IF NOT EXISTS oauth_revocation_endpoint VARCHAR,
            ADD COLUMN IF NOT EXISTS oauth_registration_client_uri VARCHAR,
            ADD COLUMN IF NOT EXISTS oauth_registration_access_token_encrypted TEXT;
    """))
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS mcp_server_user_template_idx
            ON mcp_server (user_id, template_slug)
            WHERE template_slug IS NOT NULL;
    """))
    # Backfill revocation_endpoint from the cached discovery doc so already
    # connected rows don't need a reconnect to support revocation.
    conn.execute(sa.text("""
        UPDATE mcp_server
        SET oauth_revocation_endpoint = oauth_discovery_metadata->>'revocation_endpoint'
        WHERE oauth_discovery_metadata IS NOT NULL
          AND oauth_discovery_metadata->>'revocation_endpoint' IS NOT NULL
          AND oauth_revocation_endpoint IS NULL;
    """))


def downgrade() -> None:
    pass
