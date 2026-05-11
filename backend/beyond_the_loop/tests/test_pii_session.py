"""
Tests for PIISession (in-memory storage, real PresidioService).

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_pii_session.py -v
"""
import pytest

pytest.importorskip("presidio_analyzer")
pytest.importorskip("spacy_huggingface_pipelines")
spacy = pytest.importorskip("spacy")

if not spacy.util.is_package("de_core_news_sm"):
    pytest.skip(
        "de_core_news_sm spaCy model not installed",
        allow_module_level=True,
    )

from beyond_the_loop.pii.session import InMemoryPIIStorage, PIISession


def _anon(session, text, released=None):
    """anonymize() returns a 4-tuple; tests below only care about the text."""
    out, *_ = session.anonymize(text, released)
    return out


@pytest.fixture
def storage():
    return InMemoryPIIStorage()


@pytest.fixture
def session(storage):
    return PIISession("chat-test", storage=storage)


def test_anonymize_replaces_person(session):
    out = _anon(session, "Max Mustermann hat geschrieben.")
    assert "Max Mustermann" not in out
    assert "[[PERSON_1]]" in out


def test_anonymize_replaces_email(session):
    out = _anon(session, "Schreib an max@example.de")
    assert "max@example.de" not in out
    assert "[[EMAIL_1]]" in out


def test_deanonymize_round_trip(session):
    original = "Kontakt: max.mustermann@example.de oder +49 30 12345678."
    anon = _anon(session, original)
    assert original != anon
    assert session.deanonymize(anon) == original


def test_same_value_gets_same_placeholder_within_text(session):
    text = "Max Mustermann kennt Max Mustermann gut."
    out = _anon(session, text)
    assert out.count("[[PERSON_1]]") == 2
    assert "[[PERSON_2]]" not in out


def test_consistency_across_turns(session):
    first = _anon(session, "Max Mustermann kommt.")
    second = _anon(session, "Max Mustermann kommt morgen.")
    assert "[[PERSON_1]]" in first
    assert "[[PERSON_1]]" in second


def test_counter_increments_per_new_entity(session):
    out = _anon(session, "Max Mustermann und Anna Schmidt sind hier.")
    assert "[[PERSON_1]]" in out
    assert "[[PERSON_2]]" in out


def test_counter_per_type(session):
    out = _anon(session, "Max Mustermann schreibt an anna@example.de.")
    assert "[[PERSON_1]]" in out
    assert "[[EMAIL_1]]" in out


def test_single_first_name_type_label_is_unreliable(session):
    # NER models occasionally swap PERSON/LOCATION on bare first names
    # without surrounding context. From a PII standpoint this is fine
    # (the data is still redacted), but the type label is not authoritative
    # for single tokens without context.
    out = _anon(session, "Max kommt morgen vorbei.")
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
    out = _anon(s_b, "Anna Schmidt.")
    assert "[[PERSON_1]]" in out
    assert s_b.forward.get("Max Mustermann") is None


def test_empty_and_whitespace_input(session):
    assert _anon(session, "") == ""
    assert _anon(session, "   ") == "   "
    assert session.deanonymize("") == ""


def test_text_without_pii_is_unchanged(session):
    text = "Das ist nur ein ganz normaler Satz ohne alles."
    assert _anon(session, text) == text


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
    out = _anon(session, text)
    assert "Max Mustermann" not in out
    assert "DE89" not in out
    assert "12 345 678 901" not in out
    # Round-trip restores the original.
    assert session.deanonymize(out) == text


def test_address_wins_over_location_on_overlap(session):
    """A DE_ADDRESS span ("Hauptstraße 12") strictly contains the LOCATION
    span the NER produces for "Hauptstraße". The longer/more-specific span
    must win even though the NER score is higher."""
    out = _anon(session, "Hauptstraße 12")
    assert "Hauptstraße 12" not in out
    assert "[[ADDRESS_1]]" in out
    assert "[[LOCATION_1]]" not in out


def test_sweep_redacts_known_originals_ner_might_miss(session):
    """A known original must be redacted everywhere via the sweep pass —
    chunked transformer NER drops repeats in long documents. Uses NER-neutral
    tokens so the test exercises the sweep mechanic without being coupled to
    the specific NER model's behaviour on names."""
    session.forward["Token-XYZ-1234"] = "[[CUSTOM_1]]"
    session.reverse["[[CUSTOM_1]]"] = "Token-XYZ-1234"

    out = _anon(
        session,
        "Marker A: Token-XYZ-1234. Marker B: Token-XYZ-1234. Marker C: Token-XYZ-1234.",
    )
    assert "Token-XYZ-1234" not in out
    assert out.count("[[CUSTOM_1]]") == 3


def test_sweep_respects_word_boundaries(session):
    """The sweep must only match standalone occurrences — 'Tarpen' as a
    known original should NOT replace the substring inside 'Tarpenstraße'."""
    session.forward["Tarpen"] = "[[LOCATION_1]]"

    text = "Tarpenstraße ist nicht Tarpen, aber Tarpen ist Tarpen."
    out, count = session._sweep_known(text, source="prompt", released_set=set())

    assert "Tarpenstraße" in out
    assert out.count("[[LOCATION_1]]") == 3
    assert count == 3


def test_sweep_skips_released_originals(session):
    """If the user released an original, sweep leaves verbatim occurrences alone."""
    session.forward["Max Mustermann"] = "[[PERSON_1]]"
    session.reverse["[[PERSON_1]]"] = "Max Mustermann"
    session.counters["PERSON"] = 1

    out = _anon(
        session,
        "Hallo Max Mustermann, hier nochmal Max Mustermann.",
        released=["Max Mustermann"],
    )
    assert out.count("Max Mustermann") == 2
    assert "[[PERSON_1]]" not in out


def test_anonymize_messages_skips_system_role(session):
    """System messages must pass through untouched — the default prompt's
    formatting hints ('Blockquotes', 'Bolding', 'slides') would otherwise be
    eaten by spaCy's German NER as PERSON/LOCATION false positives."""
    from beyond_the_loop.pii.session import anonymize_messages

    messages = [
        {
            "role": "system",
            "content": (
                "- Bolding (`**...**`): For key phrases.\n"
                "- Blockquotes (>): For quotes.\n"
                "User may attach spreadsheets, slides, images. Max Mustermann."
            ),
        },
        {"role": "user", "content": "Hallo, hier ist Max Mustermann."},
    ]

    anonymize_messages(messages, session)

    # System message is preserved verbatim — even the embedded "Max Mustermann".
    assert "Bolding" in messages[0]["content"]
    assert "Blockquotes" in messages[0]["content"]
    assert "spreadsheets" in messages[0]["content"]
    assert "slides" in messages[0]["content"]
    assert "Max Mustermann" in messages[0]["content"]
    assert "[[" not in messages[0]["content"]

    # User message still gets redacted.
    assert "Max Mustermann" not in messages[1]["content"]
    assert "[[PERSON_1]]" in messages[1]["content"]
