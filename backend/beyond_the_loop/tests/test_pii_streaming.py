"""
Tests for StreamingDeanonymizer — chunk-boundary handling is the critical
property, so boundaries are exercised at every character position.

No Presidio / spaCy dependency needed: the deanonymizer is pure string ops.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_pii_streaming.py -v
"""
from beyond_the_loop.pii.streaming import StreamingDeanonymizer


def _run_stream(chunks, reverse_map):
    """Helper: feed chunks, collect output, flush, return concatenated result."""
    d = StreamingDeanonymizer(reverse_map)
    out = "".join(d.feed(c) for c in chunks)
    out += d.flush()
    return out


def test_single_complete_chunk():
    out = _run_stream(["Hallo [[PERSON_1]]!"], {"[[PERSON_1]]": "Max"})
    assert out == "Hallo Max!"


def test_placeholder_split_across_two_chunks():
    d = StreamingDeanonymizer({"[[PERSON_1]]": "Max"})
    assert d.feed("Hallo [[PER") == "Hallo "
    assert d.feed("SON_1]]!") == "Max!"
    assert d.flush() == ""


def test_character_by_character_stream():
    reverse = {"[[PERSON_1]]": "Max Mustermann"}
    text = "Kontakt: [[PERSON_1]] ist erreichbar."
    out = _run_stream(list(text), reverse)
    assert out == "Kontakt: Max Mustermann ist erreichbar."


def test_multiple_placeholders_one_chunk():
    reverse = {"[[PERSON_1]]": "Max", "[[EMAIL_1]]": "max@x.de"}
    out = _run_stream(["[[PERSON_1]] schreibt an [[EMAIL_1]]"], reverse)
    assert out == "Max schreibt an max@x.de"


def test_multiple_placeholders_across_chunks():
    reverse = {"[[PERSON_1]]": "Max", "[[PERSON_2]]": "Anna"}
    d = StreamingDeanonymizer(reverse)
    assert d.feed("[[PERSON_1]] and [[") == "Max and "
    assert d.feed("PERSON_2]]") == "Anna"
    assert d.flush() == ""


def test_trailing_single_bracket_is_held():
    d = StreamingDeanonymizer({"[[PERSON_1]]": "Max"})
    # A lone `[` at end could grow into `[[` — must stay in buffer.
    assert d.feed("abc[") == "abc"
    assert d.feed("[PERSON_1]]") == "Max"


def test_trailing_double_bracket_is_held():
    d = StreamingDeanonymizer({"[[PERSON_1]]": "Max"})
    assert d.feed("abc[[") == "abc"
    assert d.feed("PERSON_1]]") == "Max"


def test_unknown_placeholder_passes_through():
    out = _run_stream(["[[UNKNOWN_99]] text"], {"[[PERSON_1]]": "Max"})
    assert out == "[[UNKNOWN_99]] text"


def test_no_placeholders_no_brackets():
    out = _run_stream(["Das ist nur normaler Text."], {"[[PERSON_1]]": "Max"})
    assert out == "Das ist nur normaler Text."


def test_empty_reverse_map_is_passthrough():
    out = _run_stream(["Hallo [[PERSON_1]]"], {})
    assert out == "Hallo [[PERSON_1]]"


def test_flush_emits_unfinished_placeholder_literally():
    # If the stream dies mid-placeholder, flush what's left raw — never drop
    # content. The unfinished bracket sequence goes to the client as-is.
    d = StreamingDeanonymizer({"[[PERSON_1]]": "Max"})
    assert d.feed("Hello [[PER") == "Hello "
    assert d.flush() == "[[PER"


def test_empty_chunk_is_safe():
    d = StreamingDeanonymizer({"[[PERSON_1]]": "Max"})
    assert d.feed("") == ""
    assert d.feed("Hallo [[PERSON_1]]") == "Hallo Max"
    assert d.flush() == ""


def test_length_ordering_prefix_collision():
    # [[PERSON_1]] is a prefix-substring risk against [[PERSON_11]]. The
    # longer one must match first, else PERSON_11 becomes "Max1".
    reverse = {"[[PERSON_1]]": "Max", "[[PERSON_11]]": "Zoe"}
    out = _run_stream(["[[PERSON_1]] und [[PERSON_11]]"], reverse)
    assert out == "Max und Zoe"


def test_single_bracket_inside_text_not_treated_as_placeholder():
    # Markdown or math can contain single `[`. Must not be buffered indefinitely.
    out = _run_stream(["a [b] c [d] e"], {"[[PERSON_1]]": "Max"})
    assert out == "a [b] c [d] e"


def test_stream_exhaustively_split_at_every_boundary():
    # Property test: for every possible split of the full text into two
    # chunks, the concatenated output is identical to the one-shot output.
    reverse = {"[[PERSON_1]]": "Max", "[[EMAIL_1]]": "max@example.de"}
    text = "Hallo [[PERSON_1]], erreichbar via [[EMAIL_1]]. Ende."
    expected = "Hallo Max, erreichbar via max@example.de. Ende."

    for i in range(len(text) + 1):
        chunks = [text[:i], text[i:]]
        assert _run_stream(chunks, reverse) == expected, (
            f"Mismatch when splitting at {i}: {text[:i]!r} | {text[i:]!r}"
        )


def test_stream_split_at_every_boundary_three_chunks():
    reverse = {"[[PERSON_1]]": "Max"}
    text = "Vor [[PERSON_1]] danach"
    expected = "Vor Max danach"

    for i in range(len(text) + 1):
        for j in range(i, len(text) + 1):
            chunks = [text[:i], text[i:j], text[j:]]
            assert _run_stream(chunks, reverse) == expected, (
                f"Mismatch at split ({i},{j})"
            )
