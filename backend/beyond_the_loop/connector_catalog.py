"""Library of pre-configured MCP connectors that users can install with one click.

Most catalog entries support DCR (RFC 7591) — the install endpoint runs
discovery + Dynamic Client Registration server-side, so the end user just
clicks "Connect" and the OAuth popup opens immediately.

Providers without DCR (Microsoft, Google) still get a catalog entry but
require the operator to deploy the corresponding MCP server and the end
user to paste their own client_id (and for Microsoft, tenant_id).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ConnectorTemplate:
    slug: str
    name: str
    description: str
    # Absolute URL to the provider's logo. Frontend renders this directly as
    # an <img src>. Living in the catalog (rather than in the frontend) keeps
    # the templates as one source of truth — adding a new connector means
    # touching one file, not two.
    icon_url: str
    server_url: str
    transport: str  # "streamable_http" | "sse"
    # May contain a `{tenant_id}` placeholder for providers (Microsoft) where
    # the OAuth authority is tenant-specific. The placeholder is substituted
    # at install time from the user-supplied tenant_id input.
    issuer_url: str
    scope: Optional[str] = None  # None = let the provider use its default scope
    extra_authorize_params: dict = field(default_factory=dict)
    # User must paste their own client_id (and optionally client_secret) at
    # install. Set this for providers that don't support DCR (Microsoft,
    # Google, etc.).
    requires_user_credentials: bool = False
    # User must paste their Entra/AAD tenant_id at install. Used to substitute
    # the `{tenant_id}` placeholder in issuer_url. Only relevant for Microsoft.
    requires_tenant_id: bool = False
    credentials_help_url: Optional[str] = None


def _build_catalog() -> list[ConnectorTemplate]:
    templates: list[ConnectorTemplate] = [
        ConnectorTemplate(
            slug="notion",
            name="Notion",
            description=(
                "Search and read your Notion workspace. Lets the assistant answer "
                "questions about pages, databases, and meeting notes you have "
                "access to."
            ),
            icon_url="https://www.notion.so/images/notion-logo-block-main.svg",
            server_url="https://mcp.notion.com/mcp",
            transport="streamable_http",
            issuer_url="https://mcp.notion.com",
            # Notion's authorize endpoint accepts no `scope` param — the workspace
            # selection during consent decides what the token sees.
            scope=None,
        ),
        ConnectorTemplate(
            slug="confluence",
            name="Confluence",
            description=(
                "Search and read your Confluence spaces and pages (and Jira "
                "issues — Atlassian's MCP server covers both products under a "
                "single connection). Lets the assistant answer questions about "
                "documentation, decisions, and tickets you have access to."
            ),
            icon_url="https://www.google.com/s2/favicons?domain=atlassian.com&sz=128",
            # `/v1/mcp` is the streamable-HTTP endpoint; the older `/v1/sse`
            # is being retired by Atlassian on 2026-06-30.
            server_url="https://mcp.atlassian.com/v1/mcp",
            transport="streamable_http",
            # Discovery returns issuer = https://cf.mcp.atlassian.com (Atlassian's
            # auth subdomain), not the MCP server's own hostname.
            issuer_url="https://cf.mcp.atlassian.com",
            # Atlassian's authorize endpoint derives scopes from the consent
            # screen — passing an explicit `scope` is not required.
            scope=None,
        ),
    ]

    # Microsoft 365 is backed by our self-hosted ms-365-mcp-server (Softeria).
    # Azure OpenAI Responses API calls the URL server-side, so it must be
    # publicly reachable with HTTPS.
    #
    # Per-environment subdomain via MS365_MCP_SERVER_URL: prod uses
    # mcp-m365.beyondtheloop.ai (the hardcoded default), staging sets the
    # env var to mcp-m365-staging.beyondtheloop.ai for isolation. Local dev
    # points it at a Cloudflare tunnel.
    ms365_url = (
        os.getenv("MS365_MCP_SERVER_URL") or "https://mcp-m365.beyondtheloop.ai/mcp"
    ).strip()
    templates.append(
        ConnectorTemplate(
            slug="microsoft-365",
            name="Microsoft 365",
            description=(
                "Access SharePoint, OneDrive, Outlook, Calendar, Teams, and "
                "Excel via your company's own Entra ID app registration. "
                "Requires a work or school account; personal Microsoft "
                "accounts are not supported. Each user must paste their "
                "tenant ID and Entra app client ID at install."
            ),
            icon_url="https://www.google.com/s2/favicons?domain=microsoft.com&sz=128",
            server_url=ms365_url,
            transport="streamable_http",
            # `{tenant_id}` is substituted at install time from the form input.
            issuer_url="https://login.microsoftonline.com/{tenant_id}/v2.0",
            # `offline_access` is Microsoft's way to issue a refresh_token —
            # without it Entra/AAD only hands out a 1-hour access_token and
            # no refresh path. Files+Sites.Read.All cover SharePoint/OneDrive
            # via Microsoft Graph; ms-365-mcp-server forwards the token to
            # Graph for every tool call.
            scope=(
                "openid email offline_access "
                "Files.Read.All Sites.Read.All User.Read"
            ),
            requires_user_credentials=True,
            requires_tenant_id=True,
            credentials_help_url=(
                "https://learn.microsoft.com/en-us/azure/active-directory/develop/"
                "quickstart-register-app"
            ),
        )
    )

    return templates


CONNECTOR_CATALOG: list[ConnectorTemplate] = _build_catalog()
CATALOG_BY_SLUG: dict[str, ConnectorTemplate] = {t.slug: t for t in CONNECTOR_CATALOG}


def get_template(slug: str) -> Optional[ConnectorTemplate]:
    return CATALOG_BY_SLUG.get(slug)
