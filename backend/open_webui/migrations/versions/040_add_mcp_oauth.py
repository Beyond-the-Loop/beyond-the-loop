"""Add OAuth columns to mcp_server

Revision ID: 040
Revises: 039
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '040'
down_revision: Union[str, None] = '039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Discovery cache, client credentials, token storage, and the in-flight
    # state for the OAuth Authorization Code round-trip. Everything is nullable
    # so it is a no-op for `bearer` and null auth_type rows.
    conn.execute(sa.text("""
        ALTER TABLE mcp_server
            ADD COLUMN oauth_issuer_url                VARCHAR,
            ADD COLUMN oauth_authorization_endpoint    VARCHAR,
            ADD COLUMN oauth_token_endpoint            VARCHAR,
            ADD COLUMN oauth_registration_endpoint     VARCHAR,
            ADD COLUMN oauth_userinfo_endpoint         VARCHAR,
            ADD COLUMN oauth_scope                     VARCHAR,
            ADD COLUMN oauth_client_id                 VARCHAR,
            ADD COLUMN oauth_client_secret_encrypted   TEXT,
            ADD COLUMN oauth_access_token_encrypted    TEXT,
            ADD COLUMN oauth_refresh_token_encrypted   TEXT,
            ADD COLUMN oauth_access_token_expires_at   BIGINT,
            ADD COLUMN oauth_granted_scope             VARCHAR,
            ADD COLUMN oauth_principal_label           VARCHAR,
            ADD COLUMN oauth_last_error                TEXT,
            ADD COLUMN oauth_discovery_metadata        JSON,
            ADD COLUMN oauth_pending_state             VARCHAR,
            ADD COLUMN oauth_pending_code_verifier     VARCHAR,
            ADD COLUMN oauth_pending_created_at        BIGINT;
    """))

    # Partial unique index: pending_state is unique among rows where it is set.
    # This is what the /oauth/callback handler looks up.
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX mcp_server_oauth_pending_state_idx
            ON mcp_server (oauth_pending_state)
            WHERE oauth_pending_state IS NOT NULL;
    """))


def downgrade() -> None:
    pass
