"""Unit tests for the tools-list reconciliation helper."""


def test_new_tools_default_enabled_true():
    from beyond_the_loop.routers.mcp_servers import reconcile_tools

    result = reconcile_tools(
        existing=None,
        discovered=[{"name": "a", "description": "A"}],
    )

    assert result == [{"name": "a", "description": "A", "enabled": True}]


def test_preserves_enabled_flag_on_known_tool():
    from beyond_the_loop.routers.mcp_servers import reconcile_tools

    result = reconcile_tools(
        existing=[{"name": "a", "description": "old", "enabled": False}],
        discovered=[{"name": "a", "description": "new"}],
    )

    assert result == [{"name": "a", "description": "new", "enabled": False}]


def test_drops_tools_missing_from_server():
    from beyond_the_loop.routers.mcp_servers import reconcile_tools

    result = reconcile_tools(
        existing=[
            {"name": "a", "description": "A", "enabled": True},
            {"name": "b", "description": "B", "enabled": False},
        ],
        discovered=[{"name": "a", "description": "A"}],
    )

    assert result == [{"name": "a", "description": "A", "enabled": True}]


def test_handles_empty_discovered_list():
    from beyond_the_loop.routers.mcp_servers import reconcile_tools

    result = reconcile_tools(
        existing=[{"name": "a", "description": "A", "enabled": True}],
        discovered=[],
    )

    assert result == []
