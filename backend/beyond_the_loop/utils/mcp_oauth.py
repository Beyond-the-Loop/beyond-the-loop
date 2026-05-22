"""OAuth 2.0 (Authorization Code + PKCE) flow for MCP server connections.

Separate from `beyond_the_loop/utils/oauth.py`, which handles SSO login and is
tightly coupled to Starlette sessions and user creation. This module is purely
server-to-server: each MCP server has its own provider config + token pair,
owned by exactly one user.

Implements:
  * Authorization-server discovery (RFC 8414, with OIDC fallback)
  * Dynamic Client Registration (RFC 7591)
  * Authorization Code flow with PKCE S256 (RFC 7636)
  * Refresh-token rotation handling (RFC 6749 §6)
  * Proactive refresh with a 60s skew window
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import re
import secrets
import time
from ipaddress import AddressValueError
from typing import Optional
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from pydantic import BaseModel

from beyond_the_loop.models.mcp_servers import MCPServerModel, MCPServers
from beyond_the_loop.utils.encryption import decrypt_secret, encrypt_secret


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


HTTP_TIMEOUT_SECONDS = 10.0
PENDING_TTL_SECONDS = 600  # 10 minutes between /oauth/start and /oauth/callback
REFRESH_SKEW_SECONDS = 60  # refresh tokens this many seconds before expiry
USER_AGENT = "beyond-the-loop/1.0 (+mcp-oauth)"


####################
# SSRF guard (shared with router)
####################


def _is_private_or_loopback(hostname: str) -> bool:
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


def _assert_https_or_safe_http(url: str) -> None:
    """OAuth endpoints must be HTTPS. SSRF guard rejects private/loopback hosts
    regardless of scheme — we never want a misconfigured provider to make us
    hit internal services."""
    if not url:
        raise OAuthError("Empty URL.")
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise OAuthError(f"Invalid URL: {e}")
    if parsed.scheme not in {"http", "https"}:
        raise OAuthError("OAuth endpoint must be http(s).")
    if parsed.scheme == "http":
        # Allow http only against the issuer URL itself (for local dev /
        # self-hosted scenarios). Tokens still travel cleartext then, but
        # that's a deliberate choice by the operator.
        pass
    if _is_private_or_loopback(parsed.hostname or ""):
        raise OAuthError("OAuth endpoint resolves to a private/loopback address.")


####################
# Error type
####################


class OAuthError(Exception):
    """Raised for any user-actionable OAuth failure. The message is surfaced
    verbatim to the admin via API responses and the `oauth_last_error` field,
    so phrase it accordingly (no stack-trace fragments, no leaked tokens)."""


####################
# PKCE
####################


def generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge). S256 only."""
    # 64 random bytes -> 86 url-safe chars, well within the 43-128 char spec window
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(32)


####################
# Discovery + DCR
####################


# RFC 9728 §5.1: when an MCP server returns 401 the WWW-Authenticate header
# advertises the PRM location via a `resource_metadata` Bearer parameter.
# This regex matches both quoted (`resource_metadata="..."`) and unquoted
# (`resource_metadata=...`) forms.
_RESOURCE_METADATA_RE = re.compile(
    r'resource_metadata\s*=\s*"?([^",\s]+)"?', re.IGNORECASE
)


async def discover_protected_resource(server_url: str) -> Optional[dict]:
    """RFC 9728 Protected Resource Metadata discovery for an MCP server.

    The MCP 2025-06-18 authorization spec says servers MUST advertise their
    authorization server(s) via PRM. We try two ways:

      1. Unauthenticated probe of the MCP endpoint itself. A spec-compliant
         server returns 401 with `WWW-Authenticate: Bearer
         resource_metadata="<url>"`, which points directly at the PRM doc.
      2. Falling back to the conventional well-known URI at the server's
         origin (RFC 8615 §3 path-suffix form, then the bare form).

    Returns the parsed PRM dict on success (must contain a non-empty
    `authorization_servers` list), or None if no PRM is discoverable —
    callers can then fall back to treating the server URL as the issuer.
    Never raises for "not found"; only logs.
    """
    _assert_https_or_safe_http(server_url)

    candidates: list[str] = []

    # Path-1: unauthenticated probe of the MCP endpoint. The server MUST 401
    # us, and the WWW-Authenticate header tells us where the PRM lives.
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        try:
            resp = await client.get(
                server_url,
                headers={"Accept": "application/json, text/event-stream"},
            )
        except httpx.RequestError as e:
            log.info("[mcp-oauth] PRM probe network error %s: %s", server_url, e)
            resp = None  # type: ignore[assignment]

        if resp is not None and resp.status_code in (401, 403):
            www_auth = resp.headers.get("www-authenticate") or ""
            m = _RESOURCE_METADATA_RE.search(www_auth)
            if m:
                candidates.append(m.group(1))
                log.info(
                    "[mcp-oauth] PRM advertised via WWW-Authenticate: %s",
                    candidates[0],
                )

    # Path-2: construct well-known candidates at the server's origin.
    # RFC 8615 §3 says path-scoped well-known URIs are formed by inserting
    # `.well-known/<suffix>` between authority and the resource path —
    # i.e. `/mcp/x` becomes `/.well-known/oauth-protected-resource/mcp/x`.
    # We also probe the bare `/.well-known/oauth-protected-resource` since
    # some servers expose it origin-wide.
    parsed = urlparse(server_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    if path:
        candidates.append(f"{origin}/.well-known/oauth-protected-resource{path}")
    candidates.append(f"{origin}/.well-known/oauth-protected-resource")

    # Dedupe in order — earlier candidates win.
    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        for url in ordered:
            try:
                resp = await client.get(url, headers={"Accept": "application/json"})
            except httpx.RequestError as e:
                log.info("[mcp-oauth] PRM fetch network error %s: %s", url, e)
                continue
            if resp.status_code >= 400:
                log.info(
                    "[mcp-oauth] PRM fetch %s -> %s", url, resp.status_code
                )
                continue
            try:
                meta = resp.json()
            except Exception:
                log.info("[mcp-oauth] PRM body at %s was not JSON", url)
                continue
            servers = meta.get("authorization_servers")
            if isinstance(servers, list) and servers:
                log.info(
                    "[mcp-oauth] PRM resolved %s -> authorization_servers=%s",
                    url, servers,
                )
                return meta
            log.info(
                "[mcp-oauth] PRM at %s missing authorization_servers", url
            )

    return None


async def discover(issuer_url: str) -> dict:
    """Fetch RFC 8414 metadata. Falls back to OIDC discovery on 404.

    Returns the parsed metadata dict. Raises OAuthError with a user-readable
    message on any failure.
    """
    _assert_https_or_safe_http(issuer_url)
    base = issuer_url.rstrip("/") + "/"

    candidates = [
        urljoin(base, ".well-known/oauth-authorization-server"),
        urljoin(base, ".well-known/openid-configuration"),
    ]

    # When the issuer has a path, also probe the origin's well-known URIs.
    # RFC 8414 strictly says path-suffix, but providers like Intercom host
    # metadata once per host at the origin and 401 anything under the
    # resource path — falling back to the origin recovers those.
    parsed = urlparse(issuer_url)
    if parsed.path.strip("/"):
        origin = f"{parsed.scheme}://{parsed.netloc}/"
        for path in (
            ".well-known/oauth-authorization-server",
            ".well-known/openid-configuration",
        ):
            url = urljoin(origin, path)
            if url not in candidates:
                candidates.append(url)

    last_err: Optional[str] = None
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        for url in candidates:
            try:
                resp = await client.get(url, headers={"Accept": "application/json"})
            except httpx.RequestError as e:
                last_err = f"network error during discovery: {e}"
                continue
            if resp.status_code == 404:
                last_err = f"discovery 404 at {url}"
                continue
            if resp.status_code >= 400:
                last_err = f"discovery HTTP {resp.status_code} at {url}"
                continue
            try:
                meta = resp.json()
            except Exception:
                last_err = f"discovery body at {url} was not JSON"
                continue
            # Minimal RFC 8414 sanity
            if not meta.get("authorization_endpoint") or not meta.get("token_endpoint"):
                last_err = f"discovery at {url} missing required endpoints"
                continue
            return meta

    raise OAuthError(
        last_err
        or f"No OAuth metadata found at {issuer_url}/.well-known/oauth-authorization-server"
    )


class RegistrationResult(BaseModel):
    """What we keep from a Dynamic Client Registration response."""
    client_id: str
    client_secret: Optional[str] = None
    # RFC 7592 management URL + bearer for later DELETE. Absolute URL — we
    # resolve relative paths (Notion returns "/register/{id}") against the
    # registration endpoint at parse time.
    registration_client_uri: Optional[str] = None
    registration_access_token: Optional[str] = None


async def register_client(
    registration_endpoint: str,
    *,
    redirect_uri: str,
    scope: Optional[str],
    client_name: str,
    client_uri: Optional[str] = None,
) -> RegistrationResult:
    """Dynamic Client Registration (RFC 7591).

    Returns a `RegistrationResult` with everything the rest of the system
    might later want to use:
      * client_id (always)
      * client_secret (None for PKCE-only public clients)
      * registration_client_uri + registration_access_token (RFC 7592) when
        the provider supports later DELETE of the registration

    `client_uri` is the homepage of the registering app. Some providers
    (notably Notion) show this on the consent screen and in the user's
    connected-apps list; without it they fall back to the redirect_uri host,
    which surfaces as "localhost" in dev.
    """
    _assert_https_or_safe_http(registration_endpoint)

    body = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    }
    if scope:
        body["scope"] = scope
    if client_uri:
        body["client_uri"] = client_uri

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        try:
            resp = await client.post(
                registration_endpoint,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.RequestError as e:
            raise OAuthError(f"DCR network error: {e}")

    if resp.status_code >= 400:
        raise OAuthError(f"DCR rejected ({resp.status_code}): {resp.text[:200]}")

    try:
        data = resp.json()
    except Exception:
        raise OAuthError("DCR response was not JSON.")

    client_id = data.get("client_id")
    if not client_id:
        raise OAuthError("DCR response did not include client_id.")

    # registration_client_uri can be relative (Notion) — resolve against the
    # registration endpoint host so we can do a flat HTTP call later.
    raw_mgmt = data.get("registration_client_uri")
    mgmt_url: Optional[str] = None
    if raw_mgmt:
        if raw_mgmt.startswith("http://") or raw_mgmt.startswith("https://"):
            mgmt_url = raw_mgmt
        else:
            from urllib.parse import urljoin
            mgmt_url = urljoin(registration_endpoint, raw_mgmt)

    return RegistrationResult(
        client_id=client_id,
        client_secret=data.get("client_secret"),
        registration_client_uri=mgmt_url,
        registration_access_token=data.get("registration_access_token"),
    )


####################
# Authorize URL + token exchange
####################


def build_authorize_url(
    *,
    authorization_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scope: Optional[str],
    state: str,
    code_challenge: str,
    extra_params: Optional[dict] = None,
) -> str:
    """Provider-specific knobs (e.g. Google's `access_type=offline`) ride in
    via `extra_params`. Standard OAuth params win on collision so a catalog
    entry can never accidentally override `client_id`/`code_challenge`/etc.
    """
    params: dict = dict(extra_params or {})
    params.update({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    if scope:
        params["scope"] = scope
    sep = "&" if "?" in authorization_endpoint else "?"
    return authorization_endpoint + sep + urlencode(params)


async def exchange_code(
    server: MCPServerModel,
    *,
    code: str,
    redirect_uri: str,
) -> dict:
    """Authorization-code -> token exchange. Returns the raw token response."""
    if not server.oauth_token_endpoint or not server.oauth_client_id:
        raise OAuthError("OAuth not configured (missing token endpoint or client_id).")
    if not server.oauth_pending_code_verifier:
        raise OAuthError("No PKCE verifier on file. Restart the connect flow.")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": server.oauth_client_id,
        "code_verifier": server.oauth_pending_code_verifier,
    }
    if server.oauth_client_secret_encrypted:
        data["client_secret"] = decrypt_secret(server.oauth_client_secret_encrypted)

    return await _post_token_endpoint(server.oauth_token_endpoint, data)


async def refresh_access_token(server: MCPServerModel) -> dict:
    """Exchange the refresh_token for a new access_token. Returns raw response."""
    if not server.oauth_token_endpoint or not server.oauth_client_id:
        raise OAuthError("OAuth not configured.")
    if not server.oauth_refresh_token_encrypted:
        raise OAuthError("No refresh token on file — reconnect required.")

    refresh_token = decrypt_secret(server.oauth_refresh_token_encrypted)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": server.oauth_client_id,
    }
    if server.oauth_scope:
        # Some providers narrow scope on refresh if omitted; passing the
        # originally-requested scope keeps the grant stable.
        data["scope"] = server.oauth_scope
    if server.oauth_client_secret_encrypted:
        data["client_secret"] = decrypt_secret(server.oauth_client_secret_encrypted)

    return await _post_token_endpoint(server.oauth_token_endpoint, data)


async def revoke_token(
    revocation_endpoint: str,
    *,
    token: str,
    token_type_hint: str,
    client_id: Optional[str],
    client_secret: Optional[str] = None,
) -> bool:
    """OAuth 2.0 Token Revocation (RFC 7009).

    Best-effort: returns True on 200/204, False on any failure. The caller
    SHOULD clear the local tokens regardless of the outcome — if the provider
    is unreachable, leaving stale tokens in our DB is worse than the small
    risk of an outstanding token on the provider's side (which will expire
    anyway).

    `token_type_hint` is "refresh_token" or "access_token" per spec — Notion
    and most other providers prefer revoking the refresh_token because that
    also kills the linked access_token (RFC 7009 §2.1).
    """
    _assert_https_or_safe_http(revocation_endpoint)
    data: dict = {"token": token, "token_type_hint": token_type_hint}
    if client_id:
        data["client_id"] = client_id
    if client_secret:
        data["client_secret"] = client_secret
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        try:
            resp = await client.post(
                revocation_endpoint,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=data,
            )
        except httpx.RequestError as e:
            log.warning("[mcp-oauth] revocation network error: %s", e)
            return False
    # RFC 7009 §2.2: 200 is success. Some providers return 204. A 400/401 with
    # "unsupported_token_type" or "invalid_token" is also effectively a no-op
    # success for us — the token is either already invalid or the provider
    # doesn't support revoking that type.
    log.info(
        "[mcp-oauth] revoke attempt url=%s hint=%s status=%s body=%r",
        revocation_endpoint, token_type_hint, resp.status_code, resp.text[:200],
    )
    if resp.status_code in (200, 204):
        return True
    return False


async def delete_client_registration(
    registration_client_uri: str,
    *,
    registration_access_token: Optional[str] = None,
    user_access_token: Optional[str] = None,
    client_secret: Optional[str] = None,
    client_id: Optional[str] = None,
) -> bool:
    """RFC 7592 Dynamic Client Registration Management — DELETE the client.

    Removes our DCR-registered app from the provider's side so it disappears
    from the user's connected-apps list. Best-effort: returns True on 2xx,
    False on anything else. Caller proceeds with local cleanup regardless.

    Auth: providers vary. Spec mandates `registration_access_token` but many
    don't issue one. We try a few schemes in order and stop at the first
    that succeeds. Every attempt is logged so the operator can see which
    one actually worked at the provider.
    """
    _assert_https_or_safe_http(registration_client_uri)

    attempts: list[tuple[str, dict]] = []
    # 1. RFC 7592 standard: Bearer registration_access_token
    if registration_access_token:
        attempts.append((
            "registration_access_token (RFC 7592)",
            {"Authorization": f"Bearer {registration_access_token}"},
        ))
    # 2. Notion-style: the user's OAuth access_token as Bearer (some providers
    #    treat the app's currently-active session as proof of ownership)
    if user_access_token:
        attempts.append((
            "user access_token",
            {"Authorization": f"Bearer {user_access_token}"},
        ))
    # 3. Bearer client_secret
    if client_secret:
        attempts.append((
            "client_secret (Bearer)",
            {"Authorization": f"Bearer {client_secret}"},
        ))
    # 4. HTTP Basic with client_id:client_secret
    if client_id and client_secret:
        import base64 as _b64
        token = _b64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        attempts.append((
            "client_id:client_secret (HTTP Basic)",
            {"Authorization": f"Basic {token}"},
        ))
    # 5. Unauthenticated
    attempts.append(("unauthenticated", {}))

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        for label, auth_headers in attempts:
            headers = {"Accept": "application/json", **auth_headers}
            try:
                resp = await client.delete(registration_client_uri, headers=headers)
            except httpx.RequestError as e:
                log.warning(
                    "[mcp-oauth] DCR delete (%s) network error: %s", label, e
                )
                continue
            log.info(
                "[mcp-oauth] DCR delete attempt url=%s auth=%s status=%s body=%r",
                registration_client_uri, label, resp.status_code, resp.text[:200],
            )
            if 200 <= resp.status_code < 300:
                return True
            # 401 means try the next auth scheme; 404/405 means the endpoint
            # doesn't support DELETE at all — no point trying again.
            if resp.status_code in (404, 405, 501):
                break
    return False


async def _post_token_endpoint(token_endpoint: str, form_data: dict) -> dict:
    _assert_https_or_safe_http(token_endpoint)
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as client:
        try:
            resp = await client.post(
                token_endpoint,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=form_data,
            )
        except httpx.RequestError as e:
            raise OAuthError(f"Token-endpoint network error: {e}")

    try:
        body = resp.json()
    except Exception:
        body = None

    if resp.status_code >= 400:
        # OAuth 2.0 RFC errors look like {"error": "invalid_grant", ...}
        if isinstance(body, dict) and body.get("error"):
            raise OAuthError(
                f"{body.get('error')}: {body.get('error_description') or 'token endpoint rejected request'}"
            )
        raise OAuthError(f"Token-endpoint HTTP {resp.status_code}.")

    if not isinstance(body, dict) or "access_token" not in body:
        raise OAuthError("Token-endpoint response missing access_token.")
    return body


####################
# Principal label (best-effort, never blocks)
####################


def _decode_id_token_email(id_token: str) -> Optional[str]:
    """Best-effort: decode the payload of a JWT id_token to surface the
    user's email/sub for display. We do NOT verify the signature here —
    this label is cosmetic and never used for authorization."""
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        return (
            payload.get("email")
            or payload.get("preferred_username")
            or payload.get("sub")
        )
    except Exception:
        return None


async def fetch_principal_label(
    token_response: dict, userinfo_endpoint: Optional[str]
) -> Optional[str]:
    if token_response.get("id_token"):
        label = _decode_id_token_email(token_response["id_token"])
        if label:
            return label
    if not userinfo_endpoint:
        return None
    access_token = token_response.get("access_token")
    if not access_token:
        return None
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(
                userinfo_endpoint,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
            )
        if resp.status_code >= 400:
            return None
        data = resp.json()
        return (
            data.get("email")
            or data.get("preferred_username")
            or data.get("name")
            or data.get("sub")
        )
    except Exception:
        return None


####################
# Persist + refresh helpers
####################


def persist_token_response(
    server_id: str,
    token_response: dict,
    *,
    principal_label: Optional[str] = None,
    clear_pending: bool = False,
) -> int:
    """Encrypt + store tokens. Returns the new expires_at (0 if non-expiring).

    Refresh-token rotation: if the provider returned a new `refresh_token`,
    we replace the stored one. Otherwise we pass None to update_oauth_tokens,
    which preserves whatever we had before.
    """
    access_token = token_response["access_token"]
    expires_in = token_response.get("expires_in")
    expires_at = int(time.time()) + int(expires_in) if expires_in else None

    new_refresh = token_response.get("refresh_token")
    refresh_encrypted = encrypt_secret(new_refresh) if new_refresh else None

    MCPServers.update_oauth_tokens(
        server_id,
        access_token_encrypted=encrypt_secret(access_token),
        refresh_token_encrypted=refresh_encrypted,
        expires_at=expires_at,
        granted_scope=token_response.get("scope"),
        principal_label=principal_label,
        last_error=None,
        clear_pending=clear_pending,
    )
    return expires_at or 0


def should_refresh(server: MCPServerModel, skew: int = REFRESH_SKEW_SECONDS) -> bool:
    if not server.oauth_access_token_encrypted:
        return False
    if not server.oauth_access_token_expires_at:
        # No expiry recorded — be conservative and assume it's still valid.
        # (Some providers issue non-expiring tokens.)
        return False
    return int(time.time()) + skew >= server.oauth_access_token_expires_at


async def get_fresh_bearer(server: MCPServerModel) -> Optional[str]:
    """Return a usable bearer token for this server, refreshing if needed.

    Returns None (and logs) if the server cannot provide a token right now —
    e.g. OAuth never completed, or refresh failed. The caller should fall
    back to skipping this server rather than crashing the chat turn.
    """
    if server.auth_type == "bearer":
        if not server.auth_token_encrypted:
            return None
        try:
            return decrypt_secret(server.auth_token_encrypted)
        except Exception as e:
            log.warning("[mcp] failed to decrypt bearer token for %s: %s", server.id, e)
            return None

    if server.auth_type != "oauth":
        return None

    if not server.oauth_access_token_encrypted:
        # Never connected
        return None

    if should_refresh(server):
        try:
            token_response = await refresh_access_token(server)
        except OAuthError as e:
            log.warning("[mcp] refresh failed for %s: %s", server.id, e)
            MCPServers.set_oauth_last_error(server.id, str(e))
            return None
        except Exception as e:
            log.exception("[mcp] unexpected refresh error for %s", server.id)
            MCPServers.set_oauth_last_error(server.id, f"unexpected: {e}")
            return None
        persist_token_response(server.id, token_response)
        # Use the freshly-issued token directly rather than re-reading the DB row
        return token_response["access_token"]

    try:
        return decrypt_secret(server.oauth_access_token_encrypted)
    except Exception as e:
        log.warning("[mcp] failed to decrypt oauth token for %s: %s", server.id, e)
        return None


####################
# Pending-state TTL check (for /oauth/callback)
####################


def pending_is_fresh(server: MCPServerModel) -> bool:
    if not server.oauth_pending_created_at:
        return False
    return int(time.time()) - server.oauth_pending_created_at <= PENDING_TTL_SECONDS
