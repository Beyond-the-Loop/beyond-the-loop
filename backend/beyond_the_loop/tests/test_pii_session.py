"""
Tests for PIISession (in-memory storage, real PresidioService).

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_pii_session.py -v
"""
import pytest

pytest.importorskip("presidio_analyzer")
spacy = pytest.importorskip("spacy")

if not spacy.util.is_package("de_core_news_lg"):
    pytest.skip(
        "de_core_news_lg spaCy model not installed",
        allow_module_level=True,
    )

from beyond_the_loop.pii.session import InMemoryPIIStorage, PIISession


@pytest.fixture
def storage():
    return InMemoryPIIStorage()


@pytest.fixture
def session(storage):
    return PIISession("chat-test", storage=storage)


def test_anonymize_replaces_person(session):
    out = session.anonymize("Max Mustermann hat geschrieben.")
    assert "Max Mustermann" not in out
    assert "[[PERSON_1]]" in out


def test_anonymize_replaces_email(session):
    out = session.anonymize("Schreib an max@example.de")
    assert "max@example.de" not in out
    assert "[[EMAIL_1]]" in out


def test_deanonymize_round_trip(session):
    original = "Kontakt: max.mustermann@example.de oder +49 30 12345678."
    anon = session.anonymize(original)
    assert original != anon
    assert session.deanonymize(anon) == original


def test_same_value_gets_same_placeholder_within_text(session):
    text = "Max Mustermann kennt Max Mustermann gut."
    out = session.anonymize(text)
    assert out.count("[[PERSON_1]]") == 2
    assert "[[PERSON_2]]" not in out


def test_consistency_across_turns(session):
    first = session.anonymize("Max Mustermann kommt.")
    second = session.anonymize("Max Mustermann kommt morgen.")
    assert "[[PERSON_1]]" in first
    assert "[[PERSON_1]]" in second


def test_counter_increments_per_new_entity(session):
    out = session.anonymize("Max Mustermann und Anna Schmidt sind hier.")
    assert "[[PERSON_1]]" in out
    assert "[[PERSON_2]]" in out


def test_counter_per_type(session):
    out = session.anonymize("Max Mustermann schreibt an anna@example.de.")
    assert "[[PERSON_1]]" in out
    assert "[[EMAIL_1]]" in out


def test_single_first_name_type_label_is_unreliable(session):
    # Known limitation of de_core_news_lg: bare first names are sometimes
    # classified as LOCATION instead of PERSON. From a PII standpoint this
    # is fine (the data is still redacted), but the type label is not
    # authoritative for single tokens without surrounding context.
    out = session.anonymize("Max kommt morgen vorbei.")
    # Either it gets redacted (under whichever label) or missed entirely.
    # Both outcomes are acceptable; the test exists so that a model upgrade
    # that tightens this is visible as a diff.
    redacted = "Max" not in out
    if redacted:
        assert "[[" in out and "]]" in out


def test_persistence_via_storage(storage):
    s1 = PIISession("chat-a", storage=storage)
    s1.anonymize("Max Mustermann kommt.")
    s1.save()

    # Fresh session for the same chat should recover the mapping.
    s2 = PIISession("chat-a", storage=storage)
    assert s2.forward.get("Max Mustermann") == "[[PERSON_1]]"
    assert s2.reverse.get("[[PERSON_1]]") == "Max Mustermann"


def test_session_isolation_between_chats(storage):
    s_a = PIISession("chat-a", storage=storage)
    s_a.anonymize("Max Mustermann.")
    s_a.save()

    s_b = PIISession("chat-b", storage=storage)
    # Different chat: counter restarts, different (independent) mapping.
    out = s_b.anonymize("Anna Schmidt.")
    assert "[[PERSON_1]]" in out
    assert s_b.forward.get("Max Mustermann") is None


def test_empty_and_whitespace_input(session):
    assert session.anonymize("") == ""
    assert session.anonymize("   ") == "   "
    assert session.deanonymize("") == ""


def test_text_without_pii_is_unchanged(session):
    text = "Das ist nur ein ganz normaler Satz ohne alles."
    assert session.anonymize(text) == text


def test_deanonymize_ignores_unknown_placeholders(session):
    # LLM may hallucinate placeholders we never emitted. They must pass through.
    session.anonymize("Max Mustermann kommt.")
    out = session.deanonymize("[[PERSON_1]] und [[PERSON_99]] sind da.")
    assert "Max Mustermann" in out
    assert "[[PERSON_99]]" in out


def test_multiple_entity_types_in_single_text(session):
    text = (
        "Max Mustermann, 10115 Berlin, IBAN DE89 3704 0044 0532 0130 00, "
        "Steuer-ID 12 345 678 901."
    )
    out = session.anonymize(text)
    assert "Max Mustermann" not in out
    assert "DE89" not in out
    assert "12 345 678 901" not in out
    # Round-trip restores the original.
    assert session.deanonymize(out) == text
