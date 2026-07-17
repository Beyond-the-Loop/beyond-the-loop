"""
Unit tests for beyond_the_loop.utils.petrofer_groups.assign_petrofer_groups_if_applicable.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_petrofer_groups.py -v
"""
from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock


# --- Heavy-dep stubs (mirrors pattern in test_companies_model.py) --------------
def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_stub_module(
    "open_webui.internal.db",
    get_db=MagicMock(),
    Base=type("Base", (), {"metadata": MagicMock()}),
)
_stub_module("open_webui.env", SRC_LOG_LEVELS={"MODELS": "INFO"})


PETROFER_COMPANY_ID = "383e3338-9883-4b3e-8dd6-d32f9a58339f"


@contextmanager
def _fake_get_db(session):
    yield session


class _FakeUser:
    def __init__(self, id: str, email: str, company_id: str):
        self.id = id
        self.email = email
        self.company_id = company_id


class _FakeGroup:
    def __init__(self, id: str, user_ids: list[str]):
        self.id = id
        self.user_ids = list(user_ids)
        self.updated_at = 0


def _install_mapping(monkeypatch, mapping: dict[str, list[str]]):
    import beyond_the_loop.utils.petrofer_groups as mod
    monkeypatch.setattr(mod, "EMAIL_TO_GROUP_IDS", mapping)
    monkeypatch.setattr(mod, "PETROFER_COMPANY_ID", PETROFER_COMPANY_ID)


def _make_db(groups_by_id: dict[str, _FakeGroup]):
    session = MagicMock()

    def _filter_by(id):
        q = MagicMock()
        q.first.return_value = groups_by_id.get(id)
        return q

    query = MagicMock()
    query.filter_by.side_effect = _filter_by
    session.query.return_value = query
    return session


def test_non_petrofer_user_is_noop(monkeypatch):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"a@x.com": ["g1"]})

    session = _make_db({})
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "a@x.com", company_id="some-other-company")
    petrofer_groups.assign_petrofer_groups_if_applicable(user)

    session.query.assert_not_called()


def test_petrofer_user_unknown_email_is_noop(monkeypatch):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"someone.else@petrofer.com": ["g1"]})

    session = _make_db({})
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "unknown@petrofer.com", PETROFER_COMPANY_ID)
    petrofer_groups.assign_petrofer_groups_if_applicable(user)

    session.query.assert_not_called()


def test_adds_user_to_all_mapped_groups(monkeypatch):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"john@petrofer.com": ["g1", "g2"]})

    g1 = _FakeGroup("g1", user_ids=[])
    g2 = _FakeGroup("g2", user_ids=["preexisting"])
    session = _make_db({"g1": g1, "g2": g2})
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "john@petrofer.com", PETROFER_COMPANY_ID)
    petrofer_groups.assign_petrofer_groups_if_applicable(user)

    assert "u1" in g1.user_ids
    assert "u1" in g2.user_ids
    assert "preexisting" in g2.user_ids
    assert g1.updated_at != 0  # bumped by the helper
    assert g2.updated_at != 0
    session.commit.assert_called()


def test_idempotent_no_duplicate_membership(monkeypatch):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"john@petrofer.com": ["g1"]})

    g1 = _FakeGroup("g1", user_ids=["u1"])  # already a member
    session = _make_db({"g1": g1})
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "john@petrofer.com", PETROFER_COMPANY_ID)
    petrofer_groups.assign_petrofer_groups_if_applicable(user)

    assert g1.user_ids.count("u1") == 1


def test_missing_group_logs_and_continues(monkeypatch, caplog):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"john@petrofer.com": ["missing", "g2"]})

    g2 = _FakeGroup("g2", user_ids=[])
    session = _make_db({"g2": g2})  # "missing" not in DB
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "john@petrofer.com", PETROFER_COMPANY_ID)
    with caplog.at_level("WARNING"):
        petrofer_groups.assign_petrofer_groups_if_applicable(user)

    assert "u1" in g2.user_ids
    assert any("missing" in rec.message for rec in caplog.records)


def test_email_normalisation(monkeypatch):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"john@petrofer.com": ["g1"]})

    g1 = _FakeGroup("g1", user_ids=[])
    session = _make_db({"g1": g1})
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "  JOHN@PETROFER.com  ", PETROFER_COMPANY_ID)
    petrofer_groups.assign_petrofer_groups_if_applicable(user)

    assert "u1" in g1.user_ids


def test_group_exception_is_swallowed(monkeypatch, caplog):
    from beyond_the_loop.utils import petrofer_groups
    _install_mapping(monkeypatch, {"john@petrofer.com": ["g_bad", "g_ok"]})

    g_ok = _FakeGroup("g_ok", user_ids=[])
    session = MagicMock()

    def _query_factory(_):
        q = MagicMock()

        def _filter_by(id):
            r = MagicMock()
            if id == "g_bad":
                r.first.side_effect = RuntimeError("db exploded")
            else:
                r.first.return_value = g_ok if id == "g_ok" else None
            return r

        q.filter_by.side_effect = _filter_by
        return q

    session.query.side_effect = _query_factory
    monkeypatch.setattr(petrofer_groups, "get_db", lambda: _fake_get_db(session))

    user = _FakeUser("u1", "john@petrofer.com", PETROFER_COMPANY_ID)
    with caplog.at_level("WARNING"):
        petrofer_groups.assign_petrofer_groups_if_applicable(user)  # must not raise

    assert "u1" in g_ok.user_ids
