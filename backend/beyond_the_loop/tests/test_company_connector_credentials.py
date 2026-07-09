"""Tests for company-level connector credential storage."""


def test_save_and_get_credentials_roundtrip(monkeypatch):
    from beyond_the_loop.routers.companies import (
        save_company_connector_credentials,
        get_company_connector_credentials,
    )

    stored = {}

    def fake_get(company_id):
        return stored.get(company_id, {})

    def fake_save(config, company_id):
        stored[company_id] = config
        return True

    monkeypatch.setattr(
        "beyond_the_loop.routers.companies.get_config", fake_get
    )
    monkeypatch.setattr(
        "beyond_the_loop.routers.companies.save_config", fake_save
    )

    save_company_connector_credentials(
        "co-1", "microsoft-365",
        client_id="cid", tenant_id="tid", client_secret="sekret",
    )

    roundtrip = get_company_connector_credentials("co-1", "microsoft-365")
    assert roundtrip == {
        "client_id": "cid",
        "tenant_id": "tid",
        "client_secret": "sekret",
    }

    # Encrypted blob must be present on disk under the encrypted key
    on_disk = stored["co-1"]["connectors"]["microsoft-365"]
    assert on_disk["client_id"] == "cid"
    assert on_disk["tenant_id"] == "tid"
    assert "client_secret_encrypted" in on_disk
    assert on_disk["client_secret_encrypted"] != "sekret"
    assert "client_secret" not in on_disk


def test_get_returns_none_when_no_config(monkeypatch):
    from beyond_the_loop.routers.companies import (
        get_company_connector_credentials,
    )
    monkeypatch.setattr(
        "beyond_the_loop.routers.companies.get_config", lambda cid: {}
    )
    assert get_company_connector_credentials("co-x", "microsoft-365") is None


def test_scrub_replaces_values_with_booleans():
    from beyond_the_loop.routers.companies import scrub_connector_credentials

    config = {
        "connectors": {
            "microsoft-365": {
                "client_id": "cid",
                "tenant_id": "tid",
                "client_secret_encrypted": "ciphertext",
            }
        }
    }
    scrubbed = scrub_connector_credentials(config)
    assert scrubbed["connectors"]["microsoft-365"] == {
        "has_client_id": True,
        "has_tenant_id": True,
        "has_client_secret": True,
    }


def test_scrub_handles_missing_fields():
    from beyond_the_loop.routers.companies import scrub_connector_credentials

    config = {"connectors": {"microsoft-365": {"client_id": "cid"}}}
    scrubbed = scrub_connector_credentials(config)
    assert scrubbed["connectors"]["microsoft-365"] == {
        "has_client_id": True,
        "has_tenant_id": False,
        "has_client_secret": False,
    }


def test_scrub_no_op_when_no_connectors():
    from beyond_the_loop.routers.companies import scrub_connector_credentials

    scrubbed = scrub_connector_credentials({"ui": {"foo": "bar"}})
    assert "connectors" not in scrubbed
