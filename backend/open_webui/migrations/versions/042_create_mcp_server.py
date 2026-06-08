"""Create mcp_server table — full schema

Consolidated initial migration for the MCP feature. Creates the
`mcp_server` table with everything the V1 release needs:

  * Core columns: id, ownership (user_id, company_id), display fields, URL,
    transport, enable flag, optional tool filter.
  * Bearer auth: auth_type + auth_token_encrypted (Fernet ciphertext).
  * OAuth Authorization Code + PKCE: discovery cache, client credentials,
    token storage with expiry + granted scope, principal label for the UI,
    in-flight PKCE/state for the /oauth/callback round-trip.
  * OAuth extras: oauth_authorize_extra_params (provider-specific
    authorize-URL params, e.g. Google's access_type=offline).
  * OAuth disconnect support: oauth_revocation_endpoint (RFC 7009) and
    oauth_registration_client_uri / oauth_registration_access_token_encrypted
    (RFC 7592 DCR management) so /oauth/disconnect can both revoke tokens
    and delete the client registration at the provider.
  * Library connectors: template_slug + partial unique index on
    (user_id, template_slug) enforcing one row per (user, template).

All operations use `IF NOT EXISTS` so re-running against a partially
migrated dev DB is safe.

Revision ID: 039
Revises: 038
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '039'
down_revision: Union[str, None] = '038'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS mcp_server (
            id                   VARCHAR PRIMARY KEY,
            user_id              VARCHAR NOT NULL
                                   REFERENCES "user"(id) ON DELETE CASCADE,
            company_id           VARCHAR NOT NULL
                                   REFERENCES company(id) ON DELETE CASCADE,

            name                 VARCHAR NOT NULL,
            description          TEXT,
            url                  VARCHAR NOT NULL,
            transport            VARCHAR NOT NULL,

            auth_type            VARCHAR,
            auth_token_encrypted TEXT,

            enabled              BOOLEAN NOT NULL DEFAULT TRUE,
            tool_filter          JSON,

            template_slug        VARCHAR,

            -- OAuth: discovery + client credentials
            oauth_issuer_url                            VARCHAR,
            oauth_authorization_endpoint                VARCHAR,
            oauth_token_endpoint                        VARCHAR,
            oauth_registration_endpoint                 VARCHAR,
            oauth_userinfo_endpoint                     VARCHAR,
            oauth_revocation_endpoint                   VARCHAR,
            oauth_scope                                 VARCHAR,
            oauth_client_id                             VARCHAR,
            oauth_client_secret_encrypted               TEXT,

            -- OAuth: RFC 7592 DCR management
            oauth_registration_client_uri               VARCHAR,
            oauth_registration_access_token_encrypted   TEXT,

            -- OAuth: tokens
            oauth_access_token_encrypted                TEXT,
            oauth_refresh_token_encrypted               TEXT,
            oauth_access_token_expires_at               BIGINT,
            oauth_granted_scope                         VARCHAR,
            oauth_principal_label                       VARCHAR,
            oauth_last_error                            TEXT,
            oauth_discovery_metadata                    JSON,
            oauth_authorize_extra_params                JSON,

            -- OAuth: in-flight Authorization Code round-trip
            oauth_pending_state                         VARCHAR,
            oauth_pending_code_verifier                 VARCHAR,
            oauth_pending_created_at                    BIGINT,

            created_at           BIGINT NOT NULL,
            updated_at           BIGINT NOT NULL
        );
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS mcp_server_company_id_idx "
        "ON mcp_server (company_id);"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS mcp_server_user_id_idx "
        "ON mcp_server (user_id);"
    ))

    # Pending OAuth state is unique among rows where it is set — the
    # /oauth/callback handler looks rows up by this column.
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS mcp_server_oauth_pending_state_idx
            ON mcp_server (oauth_pending_state)
            WHERE oauth_pending_state IS NOT NULL;
    """))

    # Library connectors: at most one row per (user, template).
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS mcp_server_user_template_idx
            ON mcp_server (user_id, template_slug)
            WHERE template_slug IS NOT NULL;
    """))


def downgrade() -> None:
    pass
