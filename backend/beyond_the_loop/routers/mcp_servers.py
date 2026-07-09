"""MCP-Server CRUD, connection test, and OAuth 2.0 (Authorization Code + PKCE).

Per-user ownership: each MCP server belongs to exactly one user. No sharing,
no admin override. Access is gated by the `workspace.mcp_connections` group
permission and by row-level ownership.
"""
import asyncio
import ipaddress
import logging
from ipaddress import AddressValueError
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from beyond_the_loop.connector_catalog import (
    CONNECTOR_CATALOG,
    ConnectorTemplate,
    get_template,
)
from beyond_the_loop.models.mcp_servers import (
    MCPServerForm,
    MCPServerModel,
    MCPServerResponse,
    MCPServers,
)
from beyond_the_loop.utils.access_control import has_permission
from beyond_the_loop.utils.encryption import decrypt_secret, encrypt_secret
from beyond_the_loop.utils import mcp_oauth
from beyond_the_loop.utils.mcp_oauth import discover_protected_resource, resolve_scopes
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import MCP_OAUTH_REDIRECT_URI
from open_webui.utils.auth import get_verified_user


log = logging.getLogger(__name__)
# Same reason as in mcp_oauth.py — keep INFO visible without depending on the
# global log-level env var.
log.setLevel(logging.INFO)

router = APIRouter()


VALID_TRANSPORTS = {"sse", "streamable_http"}


def _compute_scope_mismatch(row) -> bool:
    """Return True when the requested OAuth scopes are not fully covered by
    the scopes the provider actually granted.  Either field being absent /
    empty is treated as "no mismatch" so we don't surface false positives
    before the OAuth flow has run.
    """
    requested = set((row.oauth_scope or "").split())
    granted = set((row.oauth_granted_scope or "").split())
    return bool(requested - granted)
VALID_AUTH_TYPES = {None, "bearer", "oauth"}
TEST_CONNECTION_TIMEOUT_SECONDS = 8.0


############################
# Permission helpers
############################


def _to_response(server: MCPServerModel) -> MCPServerResponse:
    return MCPServerResponse(
        **{
            **server.model_dump(
                exclude={
                    "auth_token_encrypted",
                    "user_id",
                    "company_id",
                    "oauth_client_secret_encrypted",
                    "oauth_access_token_encrypted",
                    "oauth_refresh_token_encrypted",
                    "oauth_discovery_metadata",
                    "oauth_authorization_endpoint",
                    "oauth_token_endpoint",
                    "oauth_registration_endpoint",
                    "oauth_userinfo_endpoint",
                    "oauth_pending_state",
                    "oauth_pending_code_verifier",
                    "oauth_pending_created_at",
                }
            ),
            "has_auth_token": bool(server.auth_token_encrypted),
            "has_oauth_client_secret": bool(server.oauth_client_secret_encrypted),
            "has_oauth_access_token": bool(server.oauth_access_token_encrypted),
            "has_oauth_refresh_token": bool(server.oauth_refresh_token_encrypted),
            "scope_mismatch": _compute_scope_mismatch(server),
            "available_scopes": server.available_scopes,
        }
    )


def _validate_form(form_data: MCPServerForm) -> None:
    if form_data.transport not in VALID_TRANSPORTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transport. Must be one of: {sorted(VALID_TRANSPORTS)}",
        )
    if form_data.auth_type not in VALID_AUTH_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid auth_type. Must be one of: null, 'bearer', 'oauth'.",
        )


def _require_mcp_permission(user) -> None:
    """MCP connections require the `workspace.mcp_connections` group permission.

    Per product decision admins have no special access either — they manage their
    own connections like any other user.
    """
    if not has_permission(user.id, "workspace.mcp_connections"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )


def _require_owner(server: Optional[MCPServerModel], user) -> MCPServerModel:
    """A 404 is returned for both "doesn't exist" and "exists but not yours" so
    other users' server IDs cannot be enumerated."""
    if not server or server.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return server


############################
# SSRF guard
############################


def _is_private_or_loopback(hostname: str) -> bool:
    """Reject obvious internal targets before opening an outbound connection.

    Hostname-only check — does NOT resolve DNS. DNS rebinding is out of scope for V1;
    the doc (Abschnitt 9) flags this as known limitation.
    """
    if not hostname:
        return True
    h = hostname.lower().strip()
    if h in {"localhost", "localhost.localdomain", "0.0.0.0"}:
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except (AddressValueError, ValueError):
        return False


def _assert_url_safe(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL.")
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL scheme must be http or https.",
        )
    if _is_private_or_loopback(parsed.hostname or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL points to a private or loopback address.",
        )


############################
# Connection test
############################


class TestConnectionResult(BaseModel):
    success: bool
    transport: str
    tools: Optional[list[str]] = None
    message: Optional[str] = None


MCP_PROTOCOL_VERSION = "2025-06-18"


def _parse_jsonrpc_response(resp: httpx.Response) -> dict:
    """Streamable-HTTP MCP servers reply with either application/json OR an
    SSE event-stream that wraps one or more JSON-RPC messages. Both are valid
    per the MCP spec — handle whichever the server picked.
    """
    import json as _json

    ctype = (resp.headers.get("content-type") or "").lower()

    if "text/event-stream" in ctype:
        # Find the first SSE `data:` line that parses as a JSON-RPC message
        # carrying our `id`. Servers may emit notifications/comments before it.
        for raw_line in resp.text.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = _json.loads(payload)
            except Exception:
                continue
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                return obj
        raise ValueError(
            f"event-stream had no JSON-RPC frame; body starts: {resp.text[:120]!r}"
        )

    try:
        return resp.json()
    except Exception:
        raise ValueError(
            f"response was not valid JSON (content-type={ctype!r}); "
            f"body starts: {resp.text[:120]!r}"
        )


def _normalize_and_allowlist_mcp_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid MCP URL scheme.",
        )

    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid MCP URL host.",
        )

    return url


async def _post_jsonrpc(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    method: str,
    params: Optional[dict] = None,
    request_id: Optional[int] = 1,
) -> tuple[dict, dict]:
    """Send one JSON-RPC call. Returns (parsed_body, response_headers).

    `request_id=None` sends a notification (no response expected); the caller
    gets `({}, response_headers)` back.
    """
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params

    resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"HTTP {resp.status_code}: {resp.text[:200]}",
            request=resp.request,
            response=resp,
        )

    # Notifications: server returns 202 Accepted with empty body
    if request_id is None or resp.status_code == 202 or not resp.content:
        return {}, dict(resp.headers)
    return _parse_jsonrpc_response(resp), dict(resp.headers)


async def _run_connection_test(
    url: str, transport: str, auth_type: Optional[str], auth_token_plain: Optional[str]
) -> TestConnectionResult:
    _assert_url_safe(url)
    url = _normalize_and_allowlist_mcp_url(url)

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
    }
    if auth_type == "bearer" and auth_token_plain:
        # HTTP headers are ASCII-only (RFC 7230). Catch invisible non-ASCII
        # characters (e.g. NBSP, ü from a mis-paste) before httpx blows up
        # with an opaque UnicodeEncodeError deep in the request stack.
        if not auth_token_plain.isascii():
            bad = next((c for c in auth_token_plain if not c.isascii()), "?")
            return TestConnectionResult(
                success=False,
                transport=transport,
                message=(
                    f"Auth token contains a non-ASCII character ({bad!r}). "
                    "This usually means a stray invisible character was pasted in — "
                    "retype or re-paste the token."
                ),
            )
        headers["Authorization"] = f"Bearer {auth_token_plain}"

    if transport == "sse":
        # Real SSE introspection requires consuming an event stream; V1 just verifies
        # the endpoint accepts a request with the configured auth. Full tool listing
        # comes in a follow-up iteration.
        try:
            async with httpx.AsyncClient(
                timeout=TEST_CONNECTION_TIMEOUT_SECONDS, follow_redirects=False
            ) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                return TestConnectionResult(
                    success=False,
                    transport=transport,
                    message=f"HTTP {resp.status_code}",
                )
            return TestConnectionResult(
                success=True,
                transport=transport,
                message="Endpoint reachable. Tool listing for SSE not yet supported.",
            )
        except httpx.RequestError as e:
            return TestConnectionResult(
                success=False, transport=transport, message=f"Network error: {e}"
            )

    # Streamable HTTP — proper MCP handshake (initialize -> initialized -> tools/list).
    # Many servers (e.g. GitHub Copilot MCP) reject tools/list without a completed
    # handshake. We thread Mcp-Session-Id between calls if the server uses it.
    try:
        async with httpx.AsyncClient(timeout=TEST_CONNECTION_TIMEOUT_SECONDS) as client:
            # 1. initialize
            init_body, init_headers = await _post_jsonrpc(
                client,
                url,
                headers,
                "initialize",
                params={
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "beyond-the-loop", "version": "1.0.0"},
                },
                request_id=1,
            )
            if "error" in init_body:
                err = init_body["error"]
                return TestConnectionResult(
                    success=False,
                    transport=transport,
                    message=f"initialize failed: {err.get('message', err)}",
                )

            session_id = init_headers.get("mcp-session-id")
            session_headers = dict(headers)
            if session_id:
                session_headers["Mcp-Session-Id"] = session_id

            # 2. notifications/initialized (no id -> notification)
            await _post_jsonrpc(
                client, url, session_headers, "notifications/initialized", request_id=None
            )

            # 3. tools/list
            tools_body, _ = await _post_jsonrpc(
                client, url, session_headers, "tools/list", params={}, request_id=2
            )

    except httpx.HTTPStatusError as e:
        return TestConnectionResult(
            success=False, transport=transport, message=str(e)
        )
    except httpx.RequestError as e:
        return TestConnectionResult(
            success=False, transport=transport, message=f"Network error: {e}"
        )
    except UnicodeEncodeError as e:
        # httpx encodes outgoing headers as ASCII; a non-ASCII value (most likely
        # a copy/paste artefact in the token or the URL) reaches us here.
        return TestConnectionResult(
            success=False,
            transport=transport,
            message=(
                f"Request contained a non-ASCII character at position {e.start} "
                f"({e.object[e.start]!r}). Most often this is an invisible character "
                "in the bearer token — retype it manually."
            ),
        )
    except ValueError as e:
        return TestConnectionResult(
            success=False, transport=transport, message=f"Bad MCP response: {e}"
        )
    except Exception as e:
        return TestConnectionResult(
            success=False, transport=transport, message=f"Unexpected error: {e}"
        )

    if "error" in tools_body:
        return TestConnectionResult(
            success=False,
            transport=transport,
            message=f"MCP error: {tools_body['error'].get('message', tools_body['error'])}",
        )

    tools = tools_body.get("result", {}).get("tools", [])
    tool_names = [t.get("name") for t in tools if isinstance(t, dict) and t.get("name")]
    return TestConnectionResult(
        success=True,
        transport=transport,
        tools=tool_names,
        message=f"Discovered {len(tool_names)} tool(s).",
    )


############################
# CRUD
############################


@router.get("/", response_model=list[MCPServerResponse])
async def list_servers(user=Depends(get_verified_user)):
    _require_mcp_permission(user)
    servers = MCPServers.get_servers_owned_by_user(user.id)
    return [_to_response(s) for s in servers]


@router.post("/create", response_model=MCPServerResponse)
async def create_server(form_data: MCPServerForm, user=Depends(get_verified_user)):
    _require_mcp_permission(user)
    _validate_form(form_data)
    _assert_url_safe(form_data.url)

    if form_data.auth_type == "bearer" and not (form_data.auth_token or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bearer auth requires an auth_token.",
        )

    encrypted_token = (
        encrypt_secret(form_data.auth_token) if form_data.auth_token else None
    )

    # If no scope was provided by the user, try to discover one via PRM.
    if not form_data.oauth_scope and form_data.auth_type == "oauth":
        form_data.oauth_scope = await resolve_scopes(form_data.url)

    server = MCPServers.insert_new_server(
        user_id=user.id,
        company_id=user.company_id,
        form_data=form_data,
        auth_token_encrypted=encrypted_token,
    )
    if not server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    if form_data.auth_type == "oauth":
        await _bootstrap_oauth(server, form_data, user)
        server = MCPServers.get_server_by_id_and_user(server.id, user.id) or server

    return _to_response(server)


############################
# Connector catalog (Library)
#
# Declared BEFORE the /{server_id} routes — FastAPI matches in declaration
# order, so otherwise `GET /catalog` would be consumed by `GET /{server_id}`
# with server_id="catalog" and yield a 404 from the ownership check.
############################


class ConnectorTemplateResponse(BaseModel):
    """Public-facing template — no secrets, no internal flags."""
    slug: str
    name: str
    description: str
    icon_url: str
    server_url: str
    transport: str
    issuer_url: str
    # None means "no scope param sent to the authorize endpoint" — some
    # providers (Notion) don't accept a scope and let the user choose access
    # at consent time.
    scope: Optional[str] = None
    requires_user_credentials: bool
    requires_tenant_id: bool = False
    credentials_help_url: Optional[str] = None
    # Redirect URI the user must register with their OAuth provider. Included
    # in every template so the UI can show it for copy-paste without an extra
    # API call. Identical across templates.
    oauth_redirect_uri: str


class InstallTemplateForm(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    # Entra/AAD tenant_id — only used by templates whose issuer_url contains
    # a `{tenant_id}` placeholder (Microsoft 365).
    tenant_id: Optional[str] = None


def _template_to_response(t: ConnectorTemplate) -> ConnectorTemplateResponse:
    return ConnectorTemplateResponse(
        slug=t.slug,
        name=t.name,
        description=t.description,
        icon_url=t.icon_url,
        server_url=t.server_url,
        transport=t.transport,
        issuer_url=t.issuer_url,
        scope=t.scope,
        requires_user_credentials=t.requires_user_credentials,
        requires_tenant_id=t.requires_tenant_id,
        credentials_help_url=t.credentials_help_url,
        oauth_redirect_uri=MCP_OAUTH_REDIRECT_URI,
    )


def _resolve_issuer_url(template: ConnectorTemplate, tenant_id: Optional[str]) -> str:
    """Substitute the `{tenant_id}` placeholder in the template's issuer_url
    with the user-supplied value. Raises 400 if the template requires a
    tenant_id but none was provided.
    """
    issuer = template.issuer_url
    if "{tenant_id}" not in issuer:
        return issuer
    cleaned = (tenant_id or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required to install this connector.",
        )
    return issuer.replace("{tenant_id}", cleaned)


@router.get("/catalog", response_model=list[ConnectorTemplateResponse])
async def list_templates(user=Depends(get_verified_user)):
    """Public catalog rendered as the Library on the workspace page."""
    _require_mcp_permission(user)
    return [_template_to_response(t) for t in CONNECTOR_CATALOG]


@router.post("/catalog/{slug}/install", response_model=MCPServerResponse)
async def install_template(
    slug: str,
    form_data: InstallTemplateForm,
    user=Depends(get_verified_user),
):
    """Idempotent Library install.

    Library connectors are one-per-(user, template) — if the row already
    exists we just hand it back so the caller can run /oauth/start against
    it. Discovery + DCR only re-run if the cached client credentials are
    missing (e.g. a previous install was interrupted before DCR completed).
    """
    _require_mcp_permission(user)

    template = get_template(slug)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown connector: {slug}",
        )

    client_id = (form_data.client_id or "").strip() or None
    client_secret = (form_data.client_secret or "").strip() or None

    if template.requires_user_credentials and not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id is required to install this connector.",
        )

    # Substitute `{tenant_id}` placeholder in issuer_url (Microsoft templates).
    # Raises 400 if the template requires tenant_id but the form omitted it.
    resolved_issuer = _resolve_issuer_url(template, form_data.tenant_id)

    _assert_url_safe(template.server_url)

    # Discover required scopes via RFC 9728 PRM. Falls back to None gracefully.
    resolved_scope = await resolve_scopes(template.server_url)
    _prm = await discover_protected_resource(template.server_url)
    available = list(_prm.get("scopes_supported") or []) if _prm else None

    # Re-use the existing Library row if there is one for this (user, slug).
    existing = MCPServers.get_template_row_for_user(slug, user.id)
    if existing is not None:
        # Make sure the connector is enabled (a previous disconnect might have
        # left it disabled — we don't currently flip that, but be defensive).
        # Re-run discovery + DCR only if credentials never made it onto the row.
        if not existing.oauth_client_id:
            form = MCPServerForm(
                name=template.name,
                description=template.description,
                url=template.server_url,
                transport=template.transport,
                auth_type="oauth",
                enabled=True,
                oauth_issuer_url=resolved_issuer,
                oauth_scope=resolved_scope,
                oauth_client_id=client_id,
                oauth_client_secret=client_secret,
            )
            await _bootstrap_oauth(existing, form, user)
            existing = (
                MCPServers.get_server_by_id_and_user(existing.id, user.id)
                or existing
            )

        # Refresh available_scopes (PRM snapshot) and resolved_scope on every
        # re-install so the row stays in sync with the server's current metadata.
        # Wrapped in a 3 s timeout so a slow PRM never stalls an idempotent
        # re-install — mirrors the lazy-refresh pattern in GET /{server_id}.
        try:
            _reuse_prm = await asyncio.wait_for(
                discover_protected_resource(template.server_url), timeout=3.0
            )
            _reuse_available = (
                list(_reuse_prm.get("scopes_supported") or []) if _reuse_prm else None
            )
            _reuse_scope = await asyncio.wait_for(
                resolve_scopes(template.server_url), timeout=3.0
            )
            from open_webui.internal.db import get_db
            from beyond_the_loop.models.mcp_servers import MCPServer
            with get_db() as db:
                row = db.query(MCPServer).filter_by(
                    id=existing.id, user_id=user.id
                ).first()
                if row is not None:
                    if _reuse_available is not None:
                        row.available_scopes = _reuse_available
                    if _reuse_scope:
                        row.oauth_scope = _reuse_scope
                    db.commit()
            existing = (
                MCPServers.get_server_by_id_and_user(existing.id, user.id)
                or existing
            )
        except Exception as e:
            log.info("[mcp] PRM refresh skipped on catalog re-install for %s: %s", existing.id, e)

        return _to_response(existing)

    form = MCPServerForm(
        name=template.name,
        description=template.description,
        url=template.server_url,
        transport=template.transport,
        auth_type="oauth",
        enabled=True,
        oauth_issuer_url=resolved_issuer,
        oauth_scope=resolved_scope,
        oauth_client_id=client_id,
        oauth_client_secret=client_secret,
    )

    server = MCPServers.insert_new_server(
        user_id=user.id,
        company_id=user.company_id,
        form_data=form,
        template_slug=slug,
        available_scopes=available,
    )
    if not server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    try:
        await _bootstrap_oauth(server, form, user)
    except HTTPException:
        MCPServers.delete_server_by_id_and_user(server.id, user.id)
        raise

    if template.extra_authorize_params:
        from open_webui.internal.db import get_db
        from beyond_the_loop.models.mcp_servers import MCPServer
        with get_db() as db:
            row = db.query(MCPServer).filter_by(id=server.id, user_id=user.id).first()
            if row is not None:
                row.oauth_authorize_extra_params = dict(template.extra_authorize_params)
                db.commit()

    fresh = MCPServers.get_server_by_id_and_user(server.id, user.id)
    return _to_response(fresh or server)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(server_id: str, user=Depends(get_verified_user)):
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )

    # Best-effort PRM refresh. Never surface errors — a stale scope cache
    # just means the mismatch banner may be off until the next successful call.
    if server.auth_type == "oauth" and server.url:
        try:
            new_scope = await asyncio.wait_for(
                resolve_scopes(server.url), timeout=3.0
            )
            _prm = await asyncio.wait_for(
                discover_protected_resource(server.url), timeout=3.0
            )
            new_available = list(_prm.get("scopes_supported") or []) if _prm else None
            dirty = False
            if new_scope and new_scope != server.oauth_scope:
                dirty = True
            if new_available and new_available != server.available_scopes:
                dirty = True
            if dirty:
                from open_webui.internal.db import get_db
                from beyond_the_loop.models.mcp_servers import MCPServer
                with get_db() as db:
                    row = db.query(MCPServer).filter_by(id=server.id, user_id=user.id).first()
                    if row is not None:
                        if new_scope and new_scope != server.oauth_scope:
                            row.oauth_scope = new_scope
                        if new_available and new_available != server.available_scopes:
                            row.available_scopes = new_available
                        db.commit()
                        db.refresh(row)
                        server = MCPServers.get_server_by_id_and_user(server_id, user.id) or server
        except Exception as e:
            log.info("[mcp] PRM refresh failed for %s: %s", server.id, e)

    return _to_response(server)


@router.post("/{server_id}/update", response_model=MCPServerResponse)
async def update_server(
    server_id: str, form_data: MCPServerForm, user=Depends(get_verified_user)
):
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )
    _validate_form(form_data)
    _assert_url_safe(form_data.url)

    # Auth token semantics on update:
    #   auth_token = None or empty  -> keep existing encrypted token
    #   auth_token = "<new value>"  -> rotate (re-encrypt)
    # If the user is *clearing* the token, they should also set auth_type=None.
    rotate = bool((form_data.auth_token or "").strip())
    new_encrypted = encrypt_secret(form_data.auth_token) if rotate else None
    if form_data.auth_type is None and server.auth_token_encrypted is not None:
        # Clearing the auth — drop the stored token too
        rotate = True
        new_encrypted = None

    updated = MCPServers.update_server_by_id_and_user(
        server_id=server_id,
        user_id=user.id,
        form_data=form_data,
        auth_token_encrypted=new_encrypted,
        rotate_auth_token=rotate,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    # When switching to OAuth (or updating the issuer URL), re-run discovery
    # so the cached endpoints stay in sync. DCR only runs if we don't yet
    # have a client_id stored.
    if form_data.auth_type == "oauth" and (
        server.auth_type != "oauth"
        or server.oauth_issuer_url != updated.oauth_issuer_url
        or not updated.oauth_client_id
    ):
        await _bootstrap_oauth(updated, form_data, user)
        updated = MCPServers.get_server_by_id_and_user(server_id, user.id) or updated

    # When switching AWAY from OAuth, clear the stored tokens.
    if server.auth_type == "oauth" and form_data.auth_type != "oauth":
        MCPServers.clear_oauth_tokens(server_id, user.id)
        updated = MCPServers.get_server_by_id_and_user(server_id, user.id) or updated

    return _to_response(updated)


@router.delete("/{server_id}/delete", response_model=bool)
async def delete_server(server_id: str, user=Depends(get_verified_user)):
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )
    if server.template_slug:
        # Library connectors behave like SSO logins — you disconnect them,
        # you don't delete them. Keeps the (user, template) row idempotent.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This is a Library connector. Use Disconnect instead "
                "of Delete."
            ),
        )
    return MCPServers.delete_server_by_id_and_user(server_id, user.id)


############################
# Connection test
############################


@router.post("/test-connection", response_model=TestConnectionResult)
async def test_connection_pre_save(
    form_data: MCPServerForm, user=Depends(get_verified_user)
):
    """Test a configuration before saving — uses the plaintext token from the form."""
    _require_mcp_permission(user)
    _validate_form(form_data)
    return await _run_connection_test(
        url=form_data.url,
        transport=form_data.transport,
        auth_type=form_data.auth_type,
        auth_token_plain=form_data.auth_token,
    )


@router.post("/{server_id}/test-connection", response_model=TestConnectionResult)
async def test_connection_existing(server_id: str, user=Depends(get_verified_user)):
    """Test an already-saved server — decrypts the stored token server-side."""
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )

    if server.auth_type == "oauth" and not server.oauth_access_token_encrypted:
        return TestConnectionResult(
            success=False,
            transport=server.transport,
            message="Not connected. Click 'Connect with OAuth' first.",
        )

    auth_token_plain = await mcp_oauth.get_fresh_bearer(server)
    if server.auth_type == "oauth" and not auth_token_plain:
        # Refresh failed; surface whatever last_error we recorded.
        latest = MCPServers.get_server_by_id_and_user(server_id, user.id)
        msg = (latest.oauth_last_error if latest else None) or "Token refresh failed."
        return TestConnectionResult(
            success=False,
            transport=server.transport,
            message=f"{msg} Reconnect required.",
        )

    # Bearer is reported as 'bearer' to the test runner; OAuth becomes bearer
    # once we have the fresh token in hand.
    effective_auth_type = "bearer" if auth_token_plain else None

    return await _run_connection_test(
        url=server.url,
        transport=server.transport,
        auth_type=effective_auth_type,
        auth_token_plain=auth_token_plain,
    )


############################
# OAuth flow
############################


async def _bootstrap_oauth(
    server: MCPServerModel, form_data: MCPServerForm, user
) -> None:
    """Run discovery and (if needed) Dynamic Client Registration for an OAuth
    server right after create/update. Failure raises HTTP 400 with the OAuth
    error surfaced verbatim — the row is left in place so the admin can fix
    the issuer URL and retry."""
    # If the user did NOT pin an issuer URL, try RFC 9728 Protected Resource
    # Metadata discovery against the MCP server first — that's the MCP spec's
    # mandated way to find the authorization server for cases like GitHub's
    # MCP, where the server (api.githubcopilot.com) and the AS (github.com)
    # live on different origins. Only fall back to "issuer = server URL" when
    # PRM isn't advertised (self-hosted, single-tenant providers).
    issuer = (form_data.oauth_issuer_url or "").rstrip("/")
    if not issuer:
        prm = None
        if server.url:
            try:
                prm = await mcp_oauth.discover_protected_resource(server.url)
            except mcp_oauth.OAuthError as e:
                # PRM is best-effort — don't fail the whole bootstrap on a
                # rejected probe. Just log and fall back to server-URL issuer.
                log.info("[mcp-oauth] PRM probe rejected: %s", e)
        if prm:
            issuer = (prm.get("authorization_servers") or [None])[0]
            issuer = (issuer or "").rstrip("/")
        if not issuer:
            issuer = (server.url or "").rstrip("/")

    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth requires an issuer URL (defaults to the server URL).",
        )

    try:
        metadata = await mcp_oauth.discover(issuer)
    except mcp_oauth.OAuthError as e:
        MCPServers.set_oauth_last_error(server.id, f"discovery: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    MCPServers.update_oauth_discovery(
        server.id,
        user.id,
        issuer_url=issuer,
        authorization_endpoint=metadata.get("authorization_endpoint"),
        token_endpoint=metadata.get("token_endpoint"),
        registration_endpoint=metadata.get("registration_endpoint"),
        userinfo_endpoint=metadata.get("userinfo_endpoint"),
        revocation_endpoint=metadata.get("revocation_endpoint"),
        discovery_metadata=metadata,
    )

    # Either use the manually-pasted client credentials, or run DCR.
    if form_data.oauth_client_id:
        secret_enc = (
            encrypt_secret(form_data.oauth_client_secret)
            if form_data.oauth_client_secret
            else None
        )
        MCPServers.update_oauth_client_credentials(
            server.id,
            user.id,
            client_id=form_data.oauth_client_id,
            client_secret_encrypted=secret_enc,
        )
        return

    registration_endpoint = metadata.get("registration_endpoint")
    if not registration_endpoint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provider does not support Dynamic Client Registration. "
                "Open Advanced and paste a manually-issued client_id (and "
                "client_secret if applicable)."
            ),
        )

    try:
        # client_uri shows up next to the app name on some provider's consent
        # screens and connected-apps lists (e.g. Notion). We derive it from
        # the redirect_uri host so it's always consistent with where the
        # OAuth callback lands.
        try:
            redirect_parsed = urlparse(MCP_OAUTH_REDIRECT_URI)
            client_uri = f"{redirect_parsed.scheme}://{redirect_parsed.netloc}"
        except Exception:
            client_uri = None

        dcr = await mcp_oauth.register_client(
            registration_endpoint,
            redirect_uri=MCP_OAUTH_REDIRECT_URI,
            scope=form_data.oauth_scope,
            client_name=f"Beyond the Loop ({server.name})",
            client_uri=client_uri,
        )
    except mcp_oauth.OAuthError as e:
        MCPServers.set_oauth_last_error(server.id, f"dcr: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    MCPServers.update_oauth_client_credentials(
        server.id,
        user.id,
        client_id=dcr.client_id,
        client_secret_encrypted=encrypt_secret(dcr.client_secret) if dcr.client_secret else None,
        registration_client_uri=dcr.registration_client_uri,
        registration_access_token_encrypted=(
            encrypt_secret(dcr.registration_access_token)
            if dcr.registration_access_token
            else None
        ),
    )


class OAuthStartResponse(BaseModel):
    authorize_url: str
    state: str


@router.post("/{server_id}/oauth/start", response_model=OAuthStartResponse)
async def oauth_start(server_id: str, user=Depends(get_verified_user)):
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )

    if server.auth_type != "oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server is not configured for OAuth.",
        )
    if not server.oauth_authorization_endpoint or not server.oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth not bootstrapped — save the server first.",
        )

    # Refresh scope from PRM before building the authorize URL. Best-effort —
    # on failure we proceed with whatever scope is already on the row.
    try:
        new_scope = await resolve_scopes(server.url)
        if new_scope and new_scope != server.oauth_scope:
            from open_webui.internal.db import get_db
            from beyond_the_loop.models.mcp_servers import MCPServer
            with get_db() as db:
                row = db.query(MCPServer).filter_by(id=server.id, user_id=user.id).first()
                if row is not None:
                    row.oauth_scope = new_scope
                    db.commit()
            server = MCPServers.get_server_by_id_and_user(server.id, user.id) or server
    except Exception as e:
        log.info("[mcp] scope refresh failed before oauth/start for %s: %s", server.id, e)

    verifier, challenge = mcp_oauth.generate_pkce_pair()
    state = mcp_oauth.generate_state()

    if not MCPServers.set_oauth_pending(
        server.id, user.id, state=state, code_verifier=verifier
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not persist OAuth state.",
        )

    authorize_url = mcp_oauth.build_authorize_url(
        authorization_endpoint=server.oauth_authorization_endpoint,
        client_id=server.oauth_client_id,
        redirect_uri=MCP_OAUTH_REDIRECT_URI,
        scope=server.oauth_scope,
        state=state,
        code_challenge=challenge,
        extra_params=server.oauth_authorize_extra_params,
    )
    return OAuthStartResponse(authorize_url=authorize_url, state=state)


def _callback_html(*, ok: bool, message: str, server_id: Optional[str] = None) -> str:
    """Returns the HTML that the OAuth callback serves to the browser popup.

    Posts a message to the opener window and then closes itself. The opener
    must verify `event.origin === location.origin` before trusting the payload.
    """
    import json as _json
    payload = _json.dumps(
        {"type": "mcp-oauth-done", "success": ok, "message": message, "server_id": server_id}
    )
    # The script is intentionally tiny and contains no provider-supplied strings.
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MCP OAuth</title></head>
<body style="font-family:system-ui;padding:24px;">
<p>{'Connected.' if ok else 'Connection failed.'} You can close this window.</p>
<script>
(function() {{
  try {{
    if (window.opener) {{
      window.opener.postMessage({payload}, window.location.origin);
    }}
  }} catch (e) {{}}
  setTimeout(function() {{ window.close(); }}, 200);
}})();
</script>
</body></html>"""


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    """Unauthenticated by design — the OAuth provider redirects the user's
    browser here. The `state` lookup is the only authorization, and it is
    bound to a server + pending-row that is rotated single-use.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        # Provider-supplied error (e.g. "access_denied" when the user rejects).
        return HTMLResponse(
            _callback_html(ok=False, message=f"Provider returned error: {error}"),
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            _callback_html(ok=False, message="Missing code or state."),
            status_code=400,
        )

    server = MCPServers.get_server_by_pending_state(state)
    if not server:
        return HTMLResponse(
            _callback_html(ok=False, message="Unknown or expired state."),
            status_code=400,
        )

    if not mcp_oauth.pending_is_fresh(server):
        MCPServers.clear_oauth_pending(server.id)
        return HTMLResponse(
            _callback_html(
                ok=False,
                message="Connect attempt expired. Please try again.",
                server_id=server.id,
            ),
            status_code=400,
        )

    try:
        token_response = await mcp_oauth.exchange_code(
            server, code=code, redirect_uri=MCP_OAUTH_REDIRECT_URI
        )
    except mcp_oauth.OAuthError as e:
        MCPServers.set_oauth_last_error(server.id, f"exchange: {e}")
        MCPServers.clear_oauth_pending(server.id)
        return HTMLResponse(
            _callback_html(ok=False, message=str(e), server_id=server.id),
            status_code=400,
        )
    except Exception as e:
        log.exception("[mcp-oauth] unexpected exchange failure for %s", server.id)
        MCPServers.set_oauth_last_error(server.id, f"unexpected: {e}")
        MCPServers.clear_oauth_pending(server.id)
        return HTMLResponse(
            _callback_html(ok=False, message="Unexpected error.", server_id=server.id),
            status_code=500,
        )

    principal_label = await mcp_oauth.fetch_principal_label(
        token_response, server.oauth_userinfo_endpoint
    )

    mcp_oauth.persist_token_response(
        server.id,
        token_response,
        principal_label=principal_label,
        clear_pending=True,
    )

    return HTMLResponse(
        _callback_html(ok=True, message="Connected.", server_id=server.id),
        status_code=200,
    )


@router.post("/{server_id}/oauth/disconnect", response_model=bool)
async def oauth_disconnect(server_id: str, user=Depends(get_verified_user)):
    """Disconnect = clean slate.

    Order matters:
      1. Delete the DCR client registration at the provider (RFC 7592) WHILE
         the access_token is still valid — some providers (probably Notion)
         accept the user's access_token as auth for the management endpoint,
         which won't work after we've revoked it.
      2. Revoke the refresh_token (RFC 7009) so the access path is dead
         even if step 1 left the registration in place.
      3. Delete our local mcp_server row.

    Steps 1+2 are best-effort and produce detailed INFO logs at the
    [mcp-oauth] tag so the operator can see exactly which auth scheme
    the provider accepted.
    """
    _require_mcp_permission(user)
    server = _require_owner(
        MCPServers.get_server_by_id_and_user(server_id, user.id), user
    )

    log.info(
        "[mcp-oauth] disconnect start server_id=%s template_slug=%s "
        "has_access_token=%s has_refresh_token=%s "
        "has_revocation_endpoint=%s has_registration_client_uri=%s",
        server_id, server.template_slug,
        bool(server.oauth_access_token_encrypted),
        bool(server.oauth_refresh_token_encrypted),
        bool(server.oauth_revocation_endpoint),
        bool(server.oauth_registration_client_uri),
    )

    def _try_decrypt(blob: Optional[str]) -> Optional[str]:
        if not blob:
            return None
        try:
            return decrypt_secret(blob)
        except Exception as e:
            log.warning("[mcp-oauth] failed to decrypt blob during disconnect: %s", e)
            return None

    access_plain = _try_decrypt(server.oauth_access_token_encrypted)
    refresh_plain = _try_decrypt(server.oauth_refresh_token_encrypted)
    client_secret_plain = _try_decrypt(server.oauth_client_secret_encrypted)
    registration_access_plain = _try_decrypt(
        server.oauth_registration_access_token_encrypted
    )

    # Step 1: DCR delete — only when the provider issued a registration_access_token
    # at DCR time (RFC 7592 §3). Providers that don't issue one (Notion confirmed
    # via 404 on every auth scheme) also don't implement the DELETE endpoint, so
    # trying would just produce noise. Token revocation in Step 2 covers the
    # functional disconnect.
    if (
        server.oauth_registration_client_uri
        and registration_access_plain
    ):
        try:
            ok = await mcp_oauth.delete_client_registration(
                server.oauth_registration_client_uri,
                registration_access_token=registration_access_plain,
                user_access_token=access_plain,
                client_secret=client_secret_plain,
                client_id=server.oauth_client_id,
            )
            log.info(
                "[mcp-oauth] DCR delete result for %s: %s",
                server_id, "removed" if ok else "NOT removed",
            )
        except Exception as e:
            log.warning("[mcp-oauth] DCR delete crashed for %s: %s", server_id, e)
    else:
        log.info(
            "[mcp-oauth] DCR delete skipped for %s "
            "(no registration_access_token — provider doesn't support RFC 7592)",
            server_id,
        )

    # Step 2: revoke at provider
    if server.oauth_revocation_endpoint and refresh_plain:
        try:
            ok = await mcp_oauth.revoke_token(
                server.oauth_revocation_endpoint,
                token=refresh_plain,
                token_type_hint="refresh_token",
                client_id=server.oauth_client_id,
                client_secret=client_secret_plain,
            )
            log.info(
                f"[mcp-oauth] revoke result for {server_id}: "
                f"{'ok' if ok else 'failed'}"
            )
        except Exception as e:
            log.info(f"[mcp-oauth] revoke crashed for {server_id}: {e}")
    else:
        log.info(
            "[mcp-oauth] revoke skipped for %s "
            "(has_revocation_endpoint=%s has_refresh=%s)",
            server_id,
            bool(server.oauth_revocation_endpoint),
            bool(refresh_plain),
        )

    # Step 3: nuke the local row. Library-row delete is normally blocked by
    # delete_server's template-protection — call the model method directly
    # to bypass that check since we ARE the disconnect path.
    deleted = MCPServers.delete_server_by_id_and_user(server_id, user.id)
    log.info(f"[mcp-oauth] disconnect end server_id={server_id} local_deleted={deleted}")
    return deleted
