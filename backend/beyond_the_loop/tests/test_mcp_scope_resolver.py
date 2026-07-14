"""Unit tests for beyond_the_loop.utils.mcp_oauth.resolve_scopes."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.anyio
async def test_resolves_prm_scopes_and_appends_offline_access():
    from beyond_the_loop.utils import mcp_oauth

    prm = {
        "resource": "https://mcp.example/mcp",
        "authorization_servers": ["https://auth.example"],
        "scopes_supported": ["Files.Read.All", "User.Read"],
    }
    as_meta = {
        "issuer": "https://auth.example",
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "scopes_supported": ["openid", "email", "offline_access", "Files.Read.All"],
    }

    with patch.object(mcp_oauth, "discover_protected_resource", AsyncMock(return_value=prm)), \
         patch.object(mcp_oauth, "discover", AsyncMock(return_value=as_meta)):
        result = await mcp_oauth.resolve_scopes("https://mcp.example/mcp")

    assert result is not None
    parts = set(result.split())
    assert parts == {"Files.Read.All", "User.Read", "offline_access"}


@pytest.mark.anyio
async def test_omits_offline_access_when_refresh_token_not_supported():
    from beyond_the_loop.utils import mcp_oauth

    prm = {
        "authorization_servers": ["https://auth.example"],
        "scopes_supported": ["a", "b"],
    }
    as_meta = {
        "grant_types_supported": ["authorization_code"],  # no refresh_token
        "scopes_supported": ["a", "b", "offline_access"],
    }

    with patch.object(mcp_oauth, "discover_protected_resource", AsyncMock(return_value=prm)), \
         patch.object(mcp_oauth, "discover", AsyncMock(return_value=as_meta)):
        result = await mcp_oauth.resolve_scopes("https://mcp.example/mcp")

    assert result is not None
    assert "offline_access" not in result.split()


@pytest.mark.anyio
async def test_returns_none_when_prm_has_no_scopes():
    from beyond_the_loop.utils import mcp_oauth

    prm = {
        "authorization_servers": ["https://auth.example"],
        # scopes_supported missing entirely
    }

    with patch.object(mcp_oauth, "discover_protected_resource", AsyncMock(return_value=prm)):
        result = await mcp_oauth.resolve_scopes("https://mcp.example/mcp")

    assert result is None


@pytest.mark.anyio
async def test_returns_none_when_prm_discovery_fails():
    from beyond_the_loop.utils import mcp_oauth

    with patch.object(mcp_oauth, "discover_protected_resource", AsyncMock(return_value=None)):
        result = await mcp_oauth.resolve_scopes("https://mcp.example/mcp")

    assert result is None
