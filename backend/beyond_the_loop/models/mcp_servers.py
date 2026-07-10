import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from open_webui.internal.db import Base, get_db

log = logging.getLogger(__name__)

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, JSON, String, Text


####################
# MCP Server DB Schema
####################


class MCPServer(Base):
    __tablename__ = "mcp_server"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(String, ForeignKey("company.id", ondelete="CASCADE"), nullable=False)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=False)
    transport = Column(String, nullable=False)  # "sse" | "streamable_http"

    auth_type = Column(String, nullable=True)  # None | "bearer" | "oauth"
    auth_token_encrypted = Column(Text, nullable=True)  # Fernet ciphertext, bearer only

    enabled = Column(Boolean, nullable=False, default=True)
    tools = Column(JSON, nullable=True)  # [{name, description, enabled}]
    tools_fetched_at = Column(DateTime(timezone=True), nullable=True)

    # Catalog template this row was installed from. NULL for custom (user-added)
    # connectors. A partial unique index on (user_id, template_slug) ensures
    # there is at most one Library row per (user, template) — the install path
    # reuses the existing row instead of creating duplicates.
    template_slug = Column(String, nullable=True)

    # ---- OAuth fields (all nullable; only populated when auth_type == "oauth")

    oauth_issuer_url = Column(String, nullable=True)
    oauth_authorization_endpoint = Column(String, nullable=True)
    oauth_token_endpoint = Column(String, nullable=True)
    oauth_registration_endpoint = Column(String, nullable=True)
    oauth_userinfo_endpoint = Column(String, nullable=True)
    oauth_revocation_endpoint = Column(String, nullable=True)
    oauth_scope = Column(String, nullable=True)
    oauth_client_id = Column(String, nullable=True)
    oauth_client_secret_encrypted = Column(Text, nullable=True)
    # RFC 7592 client-management URL + bearer token; used by /oauth/disconnect
    # to DELETE the client registration on the provider when the user disconnects.
    oauth_registration_client_uri = Column(String, nullable=True)
    oauth_registration_access_token_encrypted = Column(Text, nullable=True)
    oauth_access_token_encrypted = Column(Text, nullable=True)
    oauth_refresh_token_encrypted = Column(Text, nullable=True)
    oauth_access_token_expires_at = Column(BigInteger, nullable=True)
    oauth_granted_scope = Column(String, nullable=True)
    oauth_principal_label = Column(String, nullable=True)
    oauth_last_error = Column(Text, nullable=True)
    oauth_discovery_metadata = Column(JSON, nullable=True)
    # Provider-specific authorize-URL params (e.g. Google's access_type=offline).
    # Populated from the connector catalog on /templates/{slug}/install; NULL for
    # custom OAuth servers.
    oauth_authorize_extra_params = Column(JSON, nullable=True)
    # In-flight authorization round-trip state. Cleared on success/disconnect.
    # Lookup by oauth_pending_state uses a partial unique index.
    oauth_pending_state = Column(String, nullable=True)
    oauth_pending_code_verifier = Column(String, nullable=True)
    oauth_pending_created_at = Column(BigInteger, nullable=True)

    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


####################
# Pydantic models
####################


class MCPServerModel(BaseModel):
    """Internal model — carries everything, including encrypted blobs.

    Never returned to the API; use MCPServerResponse for that.
    """

    id: str
    user_id: str
    company_id: str

    name: str
    description: Optional[str] = None
    url: str
    transport: str

    auth_type: Optional[str] = None
    auth_token_encrypted: Optional[str] = None

    enabled: bool = True
    tools: Optional[list[dict]] = None
    tools_fetched_at: Optional[datetime] = None
    template_slug: Optional[str] = None

    oauth_issuer_url: Optional[str] = None
    oauth_authorization_endpoint: Optional[str] = None
    oauth_token_endpoint: Optional[str] = None
    oauth_registration_endpoint: Optional[str] = None
    oauth_userinfo_endpoint: Optional[str] = None
    oauth_revocation_endpoint: Optional[str] = None
    oauth_scope: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret_encrypted: Optional[str] = None
    oauth_registration_client_uri: Optional[str] = None
    oauth_registration_access_token_encrypted: Optional[str] = None
    oauth_access_token_encrypted: Optional[str] = None
    oauth_refresh_token_encrypted: Optional[str] = None
    oauth_access_token_expires_at: Optional[int] = None
    oauth_granted_scope: Optional[str] = None
    oauth_principal_label: Optional[str] = None
    oauth_last_error: Optional[str] = None
    oauth_discovery_metadata: Optional[dict] = None
    oauth_authorize_extra_params: Optional[dict] = None
    oauth_pending_state: Optional[str] = None
    oauth_pending_code_verifier: Optional[str] = None
    oauth_pending_created_at: Optional[int] = None

    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


####################
# Forms (input / output)
####################


class MCPServerForm(BaseModel):
    name: str
    description: Optional[str] = None
    url: str
    transport: str  # "sse" | "streamable_http"

    auth_type: Optional[str] = None  # None | "bearer" | "oauth"
    # Bearer-token plaintext. Only on create/rotate; backend never returns it.
    auth_token: Optional[str] = None

    enabled: bool = True
    tools: Optional[list[dict]] = None  # [{name, enabled}] — admin's toggle state

    # OAuth configuration (all optional; defaults derived from `url` + DCR)
    oauth_issuer_url: Optional[str] = None
    oauth_scope: Optional[str] = None
    # Manual client credentials override (Advanced). When omitted and DCR is
    # supported by the issuer, we register a new client automatically.
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None  # plaintext on input only


class MCPServerResponse(BaseModel):
    """API response shape — never leaks token blobs or secret ciphertext.

    Servers are owned by a single user and only ever returned to that owner,
    so we do not expose `user_id`/`company_id` either.
    """

    id: str

    name: str
    description: Optional[str] = None
    url: str
    transport: str

    auth_type: Optional[str] = None
    has_auth_token: bool = False

    enabled: bool
    tools: Optional[list[dict]] = None
    tools_fetched_at: Optional[int] = None
    scope_mismatch: bool = False
    template_slug: Optional[str] = None

    # OAuth status fields (display-safe; no secrets)
    oauth_issuer_url: Optional[str] = None
    oauth_scope: Optional[str] = None
    oauth_granted_scope: Optional[str] = None
    oauth_principal_label: Optional[str] = None
    oauth_access_token_expires_at: Optional[int] = None
    oauth_last_error: Optional[str] = None
    has_oauth_client_secret: bool = False
    has_oauth_access_token: bool = False
    has_oauth_refresh_token: bool = False

    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


####################
# Table
####################


class MCPServersTable:
    def insert_new_server(
        self,
        user_id: str,
        company_id: str,
        form_data: MCPServerForm,
        auth_token_encrypted: Optional[str] = None,
        template_slug: Optional[str] = None,
    ) -> Optional[MCPServerModel]:
        now = int(time.time())
        server = MCPServerModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            company_id=company_id,
            name=form_data.name,
            description=form_data.description,
            url=form_data.url,
            transport=form_data.transport,
            auth_type=form_data.auth_type,
            auth_token_encrypted=auth_token_encrypted,
            enabled=form_data.enabled,
            tools=form_data.tools,
            template_slug=template_slug,
            oauth_issuer_url=form_data.oauth_issuer_url,
            oauth_scope=form_data.oauth_scope,
            oauth_client_id=form_data.oauth_client_id,
            created_at=now,
            updated_at=now,
        )

        try:
            with get_db() as db:
                row = MCPServer(**server.model_dump())
                db.add(row)
                db.commit()
                db.refresh(row)
                return MCPServerModel.model_validate(row)
        except Exception as e:
            log.error(f"Error creating mcp_server: {e}")
            return None

    def get_template_row_for_user(
        self, template_slug: str, user_id: str
    ) -> Optional[MCPServerModel]:
        """Idempotency lookup — at most one row per (user, template) exists."""
        if not template_slug:
            return None
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(user_id=user_id, template_slug=template_slug)
                    .first()
                )
                return MCPServerModel.model_validate(row) if row else None
        except Exception:
            return None

    def get_server_by_id_and_user(
        self, server_id: str, user_id: str
    ) -> Optional[MCPServerModel]:
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                return MCPServerModel.model_validate(row) if row else None
        except Exception:
            return None

    def get_server_by_pending_state(
        self, state: str
    ) -> Optional[MCPServerModel]:
        """Looks up a server in the middle of an OAuth round-trip by its
        pending `state` value. Used by the /oauth/callback endpoint, which
        is unauthenticated (the provider redirects the user's browser to it).
        """
        if not state:
            return None
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter(MCPServer.oauth_pending_state == state)
                    .first()
                )
                return MCPServerModel.model_validate(row) if row else None
        except Exception:
            return None

    def get_servers_owned_by_user(
        self, user_id: str, company_id: Optional[str] = None
    ) -> list[MCPServerModel]:
        """All MCP servers owned by this user."""
        with get_db() as db:
            q = db.query(MCPServer).filter(MCPServer.user_id == user_id)
            if company_id is not None:
                q = q.filter(MCPServer.company_id == company_id)
            rows = q.order_by(MCPServer.created_at.desc()).all()
            return [MCPServerModel.model_validate(r) for r in rows]

    def get_active_servers_for_user(self, user_id: str) -> list[MCPServerModel]:
        """Enabled servers owned by the user — used by the chat pipeline."""
        return [s for s in self.get_servers_owned_by_user(user_id) if s.enabled]

    def update_server_by_id_and_user(
        self,
        server_id: str,
        user_id: str,
        form_data: MCPServerForm,
        auth_token_encrypted: Optional[str] = None,
        rotate_auth_token: bool = False,
    ) -> Optional[MCPServerModel]:
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                if row is None:
                    return None

                row.name = form_data.name
                row.description = form_data.description
                row.url = form_data.url
                row.transport = form_data.transport
                row.auth_type = form_data.auth_type
                row.enabled = form_data.enabled
                if form_data.tools is not None:
                    # Admin edit: preserve description from stored row, apply incoming enabled flags
                    stored = {t["name"]: t for t in (row.tools or [])}
                    new_tools = []
                    for incoming in form_data.tools:
                        name = incoming.get("name")
                        if not name:
                            continue
                        base = stored.get(name, {"name": name, "description": ""})
                        new_tools.append({
                            "name": name,
                            "description": base.get("description", ""),
                            "enabled": bool(incoming.get("enabled", True)),
                        })
                    row.tools = new_tools
                # OAuth user-editable fields (issuer URL, scope, manual client_id).
                # Discovery cache + tokens are managed via dedicated methods below.
                row.oauth_issuer_url = form_data.oauth_issuer_url
                row.oauth_scope = form_data.oauth_scope
                # Only overwrite client_id if the form provides one; otherwise
                # preserve what DCR or a previous save populated.
                if form_data.oauth_client_id:
                    row.oauth_client_id = form_data.oauth_client_id
                row.updated_at = int(time.time())

                if rotate_auth_token:
                    row.auth_token_encrypted = auth_token_encrypted

                db.commit()
                db.refresh(row)
                return MCPServerModel.model_validate(row)
        except Exception as e:
            log.error(f"Error updating mcp_server {server_id}: {e}")
            return None

    def delete_server_by_id_and_user(self, server_id: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                db.query(MCPServer).filter_by(id=server_id, user_id=user_id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def transfer_servers_to_user(
        self, server_ids: list[str], new_user_id: str, company_id: str
    ) -> bool:
        if not server_ids:
            return True
        try:
            with get_db() as db:
                db.query(MCPServer).filter(
                    MCPServer.id.in_(server_ids),
                    MCPServer.company_id == company_id,
                ).update({"user_id": new_user_id}, synchronize_session=False)
                db.commit()
            return True
        except Exception as e:
            log.error(f"Error transferring mcp_servers to user {new_user_id}: {e}")
            return False

    ####################
    # OAuth-specific writes
    ####################

    def update_oauth_discovery(
        self,
        server_id: str,
        user_id: str,
        *,
        issuer_url: Optional[str],
        authorization_endpoint: Optional[str],
        token_endpoint: Optional[str],
        registration_endpoint: Optional[str],
        userinfo_endpoint: Optional[str],
        revocation_endpoint: Optional[str],
        discovery_metadata: Optional[dict],
    ) -> bool:
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                if row is None:
                    return False
                row.oauth_issuer_url = issuer_url
                row.oauth_authorization_endpoint = authorization_endpoint
                row.oauth_token_endpoint = token_endpoint
                row.oauth_registration_endpoint = registration_endpoint
                row.oauth_userinfo_endpoint = userinfo_endpoint
                row.oauth_revocation_endpoint = revocation_endpoint
                row.oauth_discovery_metadata = discovery_metadata
                row.updated_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error updating oauth discovery for {server_id}: {e}")
            return False

    def update_oauth_client_credentials(
        self,
        server_id: str,
        user_id: str,
        *,
        client_id: str,
        client_secret_encrypted: Optional[str],
        registration_client_uri: Optional[str] = None,
        registration_access_token_encrypted: Optional[str] = None,
    ) -> bool:
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                if row is None:
                    return False
                row.oauth_client_id = client_id
                row.oauth_client_secret_encrypted = client_secret_encrypted
                row.oauth_registration_client_uri = registration_client_uri
                row.oauth_registration_access_token_encrypted = (
                    registration_access_token_encrypted
                )
                row.updated_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error updating oauth client for {server_id}: {e}")
            return False

    def set_oauth_pending(
        self,
        server_id: str,
        user_id: str,
        *,
        state: str,
        code_verifier: str,
    ) -> bool:
        """Stash the in-flight PKCE/state for /oauth/callback to reclaim."""
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                if row is None:
                    return False
                row.oauth_pending_state = state
                row.oauth_pending_code_verifier = code_verifier
                row.oauth_pending_created_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error setting oauth pending for {server_id}: {e}")
            return False

    def clear_oauth_pending(self, server_id: str) -> None:
        try:
            with get_db() as db:
                row = db.query(MCPServer).filter_by(id=server_id).first()
                if row is None:
                    return
                row.oauth_pending_state = None
                row.oauth_pending_code_verifier = None
                row.oauth_pending_created_at = None
                db.commit()
        except Exception as e:
            log.error(f"Error clearing oauth pending for {server_id}: {e}")

    def update_oauth_tokens(
        self,
        server_id: str,
        *,
        access_token_encrypted: Optional[str],
        refresh_token_encrypted: Optional[str],
        expires_at: Optional[int],
        granted_scope: Optional[str],
        principal_label: Optional[str] = None,
        last_error: Optional[str] = None,
        clear_pending: bool = False,
    ) -> bool:
        """Persist the result of a token-endpoint exchange or refresh.

        `refresh_token_encrypted=None` is interpreted as "keep existing" so that
        providers which don't return a new refresh_token on rotation don't drop
        the one we already have. To explicitly delete tokens (disconnect),
        pass empty-string placeholders or use `clear_oauth_tokens`.
        """
        try:
            with get_db() as db:
                row = db.query(MCPServer).filter_by(id=server_id).first()
                if row is None:
                    return False
                row.oauth_access_token_encrypted = access_token_encrypted
                if refresh_token_encrypted is not None:
                    row.oauth_refresh_token_encrypted = refresh_token_encrypted
                row.oauth_access_token_expires_at = expires_at
                if granted_scope is not None:
                    row.oauth_granted_scope = granted_scope
                if principal_label is not None:
                    row.oauth_principal_label = principal_label
                row.oauth_last_error = last_error
                if clear_pending:
                    row.oauth_pending_state = None
                    row.oauth_pending_code_verifier = None
                    row.oauth_pending_created_at = None
                row.updated_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error updating oauth tokens for {server_id}: {e}")
            return False

    def set_oauth_last_error(self, server_id: str, message: str) -> None:
        try:
            with get_db() as db:
                row = db.query(MCPServer).filter_by(id=server_id).first()
                if row is None:
                    return
                row.oauth_last_error = message
                db.commit()
        except Exception as e:
            log.error(f"Error setting oauth last_error for {server_id}: {e}")

    def clear_oauth_tokens(self, server_id: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                row = (
                    db.query(MCPServer)
                    .filter_by(id=server_id, user_id=user_id)
                    .first()
                )
                if row is None:
                    return False
                row.oauth_access_token_encrypted = None
                row.oauth_refresh_token_encrypted = None
                row.oauth_access_token_expires_at = None
                row.oauth_granted_scope = None
                row.oauth_principal_label = None
                row.oauth_last_error = None
                row.oauth_pending_state = None
                row.oauth_pending_code_verifier = None
                row.oauth_pending_created_at = None
                row.updated_at = int(time.time())
                db.commit()
                return True
        except Exception as e:
            log.error(f"Error clearing oauth tokens for {server_id}: {e}")
            return False


MCPServers = MCPServersTable()
