"""
Integration tests for PresidioService (German PII detection).

Requires presidio-analyzer, presidio-anonymizer, spacy-huggingface-pipelines,
and the de_core_news_sm spaCy model. The HF transformer NER model
(Davlan/xlm-roberta-base-ner-hrl) is downloaded on first use.
Run with:

    pip install -r backend/requirements.txt
    python -m spacy download de_core_news_sm
    cd backend
    pytest beyond_the_loop/tests/test_pii_service.py -v
"""
import pytest

pytest.importorskip("presidio_analyzer")
pytest.importorskip("spacy_huggingface_pipelines")
spacy = pytest.importorskip("spacy")

if not spacy.util.is_package("de_core_news_sm"):
    pytest.skip(
        "de_core_news_sm spaCy model not installed — run: python -m spacy download de_core_news_sm",
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


def test_organization_detected(service):
    results = service.analyze("Ich arbeite bei Siemens AG.")
    assert "ORGANIZATION" in _types(results)


def test_person_span_extends_into_german_surname(service):
    """When subword alignment drops the surname half ('Dücker'), the
    post-processing step extends the PERSON span to cover the full name."""
    text = "Geschäftsführer: Thore Dücker schrieb."
    results = service.analyze(text)
    persons = [text[r.start:r.end] for r in results if r.entity_type == "PERSON"]
    assert any("Dücker" in p for p in persons), f"Dücker leaked: {persons}"


def test_person_span_does_not_extend_into_lowercase_word(service):
    """Don't extend across lowercase words (verbs, articles)."""
    text = "Anna geht nach Hause."
    results = service.analyze(text)
    persons = [text[r.start:r.end] for r in results if r.entity_type == "PERSON"]
    for p in persons:
        assert "geht" not in p, f"unexpectedly extended into verb: {p}"


def test_empty_text(service):
    assert service.analyze("") == []
    assert service.analyze("   ") == []


def test_person_lowercase_detected(service):
    """XLM-R's SentencePiece tokenisation handles lowercase proper nouns
    where the cased mBERT model failed."""
    results = service.analyze("ich heiße anna mustermann.")
    assert "PERSON" in _types(results)


def test_location_lowercase_detected(service):
    results = service.analyze("ich wohne in hamburg.")
    assert "LOCATION" in _types(results)


def test_email_with_special_chars_detected(service):
    """Hyphens, plus, dots in local/domain part — broader pattern than
    Presidio's default."""
    for email in (
        "lea_schneider-hr@corp-example.test",
        "claire.dubois+privat@samplemail.test",
        "oliver.hansen@demo-company.test",
    ):
        results = service.analyze(f"Schreib an {email}")
        assert any(
            r.entity_type == "EMAIL_ADDRESS"
            and r.start <= f"Schreib an {email}".index(email)
            and r.end >= f"Schreib an {email}".index(email) + len(email)
            for r in results
        ), f"email not fully detected: {email}"


def test_email_wins_over_url_overlap(service):
    """URL recognizer used to fragment emails — the custom email recognizer
    has a longer span and higher score so it wins overlap resolution."""
    results = service.analyze("Mail: claire.dubois+privat@samplemail.test")
    types = _types(results)
    assert "EMAIL_ADDRESS" in types


def test_date_dmy_detected(service):
    results = service.analyze("Geburtsdatum: 14.03.1987.")
    assert "DATE_TIME" in _types(results)


def test_date_iso_detected(service):
    results = service.analyze("geboren am 1991-11-08")
    assert "DATE_TIME" in _types(results)


def test_date_word_de_detected(service):
    results = service.analyze("Termin am 14. März 2026.")
    assert "DATE_TIME" in _types(results)


def test_date_word_en_dmy_detected(service):
    results = service.analyze("Vesting starts 01 January 2026.")
    assert "DATE_TIME" in _types(results)


def test_date_word_en_mdy_detected(service):
    results = service.analyze("Effective March 14, 2026.")
    assert "DATE_TIME" in _types(results)


def test_phone_us_detected(service):
    results = service.analyze("Call me at (415) 555-0132 anytime.")
    assert "PHONE_NUMBER" in _types(results)


def test_bic_detected(service):
    results = service.analyze("BIC: COBADEFFXXX")
    assert "BIC_CODE" in _types(results)


def test_bic_does_not_match_lowercase_word(service):
    """Common 8-letter German words must NOT be flagged as BIC — recognizer
    is case-sensitive."""
    results = service.analyze("Das ist nur ein normaler Satz ohne alles.")
    assert "BIC_CODE" not in _types(results)


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
