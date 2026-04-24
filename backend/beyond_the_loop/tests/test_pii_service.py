"""
Integration tests for PresidioService (German PII detection).

Requires presidio-analyzer, presidio-anonymizer, and the de_core_news_lg
spaCy model. Run with:

    pip install -r backend/requirements.txt
    python -m spacy download de_core_news_lg
    cd backend
    pytest beyond_the_loop/tests/test_pii_service.py -v
"""
import pytest

pytest.importorskip("presidio_analyzer")
spacy = pytest.importorskip("spacy")

if not spacy.util.is_package("de_core_news_lg"):
    pytest.skip(
        "de_core_news_lg spaCy model not installed — run: python -m spacy download de_core_news_lg",
        allow_module_level=True,
    )

from beyond_the_loop.pii.service import PresidioService


@pytest.fixture(scope="module")
def service():
    return PresidioService.instance()


def _types(results):
    return {r.entity_type for r in results}


def test_person_detected(service):
    results = service.analyze("Ich heiße Max Mustermann.")
    assert "PERSON" in _types(results)


def test_location_detected(service):
    results = service.analyze("Ich wohne in Berlin.")
    assert "LOCATION" in _types(results)


def test_email_detected(service):
    results = service.analyze("Kontakt: max.mustermann@example.de")
    assert "EMAIL_ADDRESS" in _types(results)


def test_phone_de_detected(service):
    results = service.analyze("Meine Nummer ist +49 30 12345678.")
    assert "PHONE_NUMBER" in _types(results)


def test_iban_detected(service):
    results = service.analyze("Meine IBAN lautet DE89 3704 0044 0532 0130 00.")
    assert "IBAN_CODE" in _types(results)


def test_credit_card_detected(service):
    results = service.analyze("Meine Kreditkarte ist 4111 1111 1111 1111.")
    assert "CREDIT_CARD" in _types(results)


def test_steuer_id_detected(service):
    results = service.analyze("Meine Steuer-ID ist 12 345 678 901.")
    assert "DE_STEUER_ID" in _types(results)


def test_sv_nummer_detected(service):
    results = service.analyze("Meine Sozialversicherungsnummer ist 65 170839 W 003.")
    assert "DE_SOZIALVERSICHERUNGSNUMMER" in _types(results)


def test_address_street_detected(service):
    results = service.analyze("Ich wohne in der Musterstraße 12.")
    assert "DE_ADDRESS" in _types(results)


def test_address_plz_city_detected(service):
    results = service.analyze("Meine Anschrift: 10115 Berlin.")
    assert "DE_ADDRESS" in _types(results)


def test_organization_not_detected(service):
    results = service.analyze("Ich arbeite bei Siemens AG.")
    assert "ORGANIZATION" not in _types(results)


def test_empty_text(service):
    assert service.analyze("") == []
    assert service.analyze("   ") == []


def test_multiple_entities_combined(service):
    text = (
        "Max Mustermann wohnt in der Musterstraße 12, 10115 Berlin. "
        "Erreichbar unter max@example.de oder +49 30 12345678."
    )
    types = _types(service.analyze(text))
    assert "PERSON" in types
    assert "EMAIL_ADDRESS" in types
    assert "PHONE_NUMBER" in types
    assert "DE_ADDRESS" in types
