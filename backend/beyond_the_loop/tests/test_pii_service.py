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


def test_iban_detected(service):
    results = service.analyze("Meine IBAN lautet DE89 3704 0044 0532 0130 00.")
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


def _spans_of_type(results, etype):
    return [r for r in results if r.entity_type == etype]


def _texts(results, text):
    return [text[r.start:r.end] for r in results]


def test_full_name_not_fragmented(service):
    text = "Mein Name ist Phil Szalay."
    persons = _spans_of_type(service.analyze(text), "private_person")
    captured = _texts(persons, text)
    assert any("Phil Szalay" in c for c in captured), captured


def test_surname_with_subword_split_not_truncated(service):
    text = "Ansprechpartner: Thore Dücker."
    persons = _spans_of_type(service.analyze(text), "private_person")
    captured = _texts(persons, text)
    assert any("Thore Dücker" in c for c in captured), captured


def test_full_address_single_span(service):
    text = "Adresse: Eifflerstraße 47, 22769 Hamburg, Deutschland."
    addresses = _spans_of_type(service.analyze(text), "private_address")
    captured = _texts(addresses, text)
    assert any("Eifflerstraße 47" in c and "Hamburg" in c for c in captured), captured


def test_date_year_not_truncated(service):
    text = "Datum: 01 January 2026."
    dates = _spans_of_type(service.analyze(text), "private_date")
    captured = _texts(dates, text)
    assert any("2026" in c for c in captured), captured


def test_no_punctuation_only_spans(service):
    text = "Phil Szalay wohnt in der Eifflerstraße 47, 22769 Hamburg, Deutschland."
    results = service.analyze(text)
    for r in results:
        captured = text[r.start:r.end]
        assert any(c.isalnum() for c in captured), f"punctuation-only span: {captured!r}"


def test_no_cross_entity_merge(service):
    text = "Phil Szalay, Eifflerstraße 47."
    results = service.analyze(text)
    for r in results:
        captured = text[r.start:r.end]
        if r.entity_type == "private_person":
            assert "Eifflerstraße" not in captured, captured
        if r.entity_type == "private_address":
            assert "Phil" not in captured and "Szalay" not in captured, captured
