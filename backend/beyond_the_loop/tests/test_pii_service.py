"""
Integration tests for PrivacyFilterService (openai/privacy-filter).

The model is downloaded from HuggingFace on first run. Subsequent runs load
from the local cache.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_pii_service.py -v
"""
import pytest

from beyond_the_loop.pii.service import PrivacyFilterService


@pytest.fixture(scope="module")
def service():
    return PrivacyFilterService.instance()


def _types(results):
    return {r.entity_type for r in results}


def test_person_detected(service):
    results = service.analyze("Ich heiße Max Mustermann.")
    assert "private_person" in _types(results)


def test_email_detected(service):
    results = service.analyze("Kontakt: max.mustermann@example.de")
    assert "private_email" in _types(results)


def test_phone_de_detected(service):
    results = service.analyze("Meine Nummer ist +49 30 12345678.")
    assert "private_phone" in _types(results)


def test_address_detected(service):
    results = service.analyze("Ich wohne in der Musterstraße 12, 10115 Berlin.")
    assert "private_address" in _types(results)


def test_date_detected(service):
    results = service.analyze("Geburtsdatum: 14.03.1987.")
    assert "private_date" in _types(results)


def test_url_detected(service):
    results = service.analyze("Meine Website: https://max-mustermann.de")
    assert "private_url" in _types(results)


def test_iban_detected(service):
    results = service.analyze("Meine IBAN lautet DE89 3704 0044 0532 0130 00.")
    assert "account_number" in _types(results)


def test_credit_card_detected(service):
    results = service.analyze("Meine Kreditkarte ist 4111 1111 1111 1111.")
    assert "account_number" in _types(results)


def test_secret_detected(service):
    results = service.analyze("Mein API-Key lautet sk-abc123XYZsecretkey456.")
    assert "secret" in _types(results)


def test_empty_text(service):
    assert service.analyze("") == []
    assert service.analyze("   ") == []


def test_multiple_entities_combined(service):
    text = (
        "Max Mustermann wohnt in der Musterstraße 12, 10115 Berlin. "
        "Erreichbar unter max@example.de oder +49 30 12345678."
    )
    types = _types(service.analyze(text))
    assert "private_person" in types
    assert "private_email" in types
    assert "private_phone" in types


def test_whitespace_only_spans_dropped(service):
    results = service.analyze("   ")
    assert results == []
