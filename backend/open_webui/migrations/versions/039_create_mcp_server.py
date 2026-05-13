"""Create mcp_server table

Revision ID: 039
Revises: 038
Create Date: 2026-05-12 00:00:00.000000

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
        CREATE TABLE mcp_server (
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

            created_at           BIGINT NOT NULL,
            updated_at           BIGINT NOT NULL
        );
    """))

    conn.execute(sa.text(
        "CREATE INDEX mcp_server_company_id_idx ON mcp_server (company_id);"
    ))
    conn.execute(sa.text(
        "CREATE INDEX mcp_server_user_id_idx ON mcp_server (user_id);"
    ))


def downgrade() -> None:
    pass
