"""
Custom Presidio recognizers for German-specific PII.

Detects:
- EMAIL_ADDRESS — broader/higher-score pattern than Presidio's default so it
  wins over URL matches on overlap (URL was fragmenting emails)
- DATE_TIME — DE/ISO/US date formats restricted to 1900-2099
- BIC_CODE — SWIFT/BIC (ISO 9362)
- DE_STEUER_ID — Steuerliche Identifikationsnummer (11 digits, first digit 1-9)
- DE_SOZIALVERSICHERUNGSNUMMER — 2d + 6d (birthdate) + 1 letter + 3d
- DE_ADDRESS — German street+number and PLZ+city patterns
"""
from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

# Presidio defaults to re.IGNORECASE — keep that for most recognizers, but BIC
# is defined as uppercase ISO 9362, so case-insensitive matching turns common
# 8-letter German words ("normaler", "schreiben", …) into false positives.
_CASE_SENSITIVE_FLAGS = re.DOTALL | re.MULTILINE


def _email_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern(
            name="email",
            regex=r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            score=0.95,
        ),
    ]
    context = ["E-Mail", "Email", "Mail", "@"]
    return PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        supported_language="de",
        patterns=patterns,
        context=context,
    )


def _date_recognizer() -> PatternRecognizer:
    year = r"(?:19|20)\d{2}"
    months_de = (
        "Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|"
        "September|Oktober|November|Dezember|"
        "Jan|Feb|Mär|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez"
    )
    months_en = (
        "January|February|March|April|May|June|July|August|"
        "September|October|November|December|"
        "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    )
    day = r"(?:0?[1-9]|[12]\d|3[01])"
    patterns = [
        # DE numeric: 14.03.1987 / 14-03-1987 / 14/03/1987
        Pattern(
            name="dmy_numeric",
            regex=rf"\b{day}[\./\-](?:0?[1-9]|1[0-2])[\./\-]{year}\b",
            score=0.5,
        ),
        # ISO: 1987-03-14 / 1987/03/14
        Pattern(
            name="ymd_iso",
            regex=rf"\b{year}[\-/](?:0?[1-9]|1[0-2])[\-/]{day}\b",
            score=0.5,
        ),
        # US numeric: 07/22/1979
        Pattern(
            name="mdy_us",
            regex=rf"\b(?:0?[1-9]|1[0-2])/{day}/{year}\b",
            score=0.4,
        ),
        # 14. März 1987 / 14 Maerz 2025
        Pattern(
            name="dmy_word_de",
            regex=rf"\b{day}\.?\s+(?:{months_de})\.?\s+{year}\b",
            score=0.7,
        ),
        # 01 January 2026 / 1st January 2026 / 14th Mar 2025
        Pattern(
            name="dmy_word_en",
            regex=rf"\b{day}(?:st|nd|rd|th)?\s+(?:{months_en})\.?\s+{year}\b",
            score=0.7,
        ),
        # January 14, 2026 / Mar 14 2026
        Pattern(
            name="mdy_word_en",
            regex=rf"\b(?:{months_en})\.?\s+{day}(?:st|nd|rd|th)?,?\s+{year}\b",
            score=0.7,
        ),
    ]
    context = ["geboren", "Geburt", "Geburtsdatum", "DOB", "geb", "Datum", "née", "fecha", "born", "date"]
    return PatternRecognizer(
        supported_entity="DATE_TIME",
        supported_language="de",
        patterns=patterns,
        context=context,
    )


def _bic_recognizer() -> PatternRecognizer:
    # ISO 9362: 4 bank + 2 country letters + 2 alphanum location + optional 3 branch.
    patterns = [
        Pattern(
            name="bic",
            regex=r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
            score=0.4,
        ),
    ]
    context = ["BIC", "SWIFT", "Swift-Code"]
    return PatternRecognizer(
        supported_entity="BIC_CODE",
        supported_language="de",
        patterns=patterns,
        context=context,
        global_regex_flags=_CASE_SENSITIVE_FLAGS,
    )


def _steuer_id_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern(
            name="de_steuer_id",
            # Score 0.6 so the structured 11-digit ID wins overlap resolution
            # against PhoneRecognizer (default 0.4) on the same digit run.
            regex=r"\b[1-9](?:[\s\-]?\d){10}\b",
            score=0.6,
        ),
    ]
    context = [
        "Steuer-ID",
        "Steueridentifikationsnummer",
        "Steuerliche Identifikationsnummer",
        "Steuer-IdNr",
        "IdNr",
        "TIN",
    ]
    return PatternRecognizer(
        supported_entity="DE_STEUER_ID",
        supported_language="de",
        patterns=patterns,
        context=context,
    )


def _sozialversicherungsnummer_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern(
            name="de_sv_nr",
            regex=r"\b\d{2}\s?\d{6}\s?[A-ZÄÖÜ]\s?\d{3}\b",
            score=0.5,
        ),
    ]
    context = [
        "Sozialversicherungsnummer",
        "SV-Nummer",
        "SVN",
        "Rentenversicherungsnummer",
        "RV-Nummer",
    ]
    return PatternRecognizer(
        supported_entity="DE_SOZIALVERSICHERUNGSNUMMER",
        supported_language="de",
        patterns=patterns,
        context=context,
    )


def _address_recognizer() -> PatternRecognizer:
    street_pattern = (
        r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+?"
        r"(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|ufer|chaussee)"
        r"\s+\d{1,4}[a-zA-Z]?\b"
    )
    plz_city_pattern = r"\b\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{2,}\b"

    patterns = [
        Pattern(name="de_street", regex=street_pattern, score=0.5),
        Pattern(name="de_plz_city", regex=plz_city_pattern, score=0.4),
    ]
    context = ["Adresse", "Anschrift", "wohnhaft", "Wohnort", "Straße", "Postleitzahl"]
    return PatternRecognizer(
        supported_entity="DE_ADDRESS",
        supported_language="de",
        patterns=patterns,
        context=context,
    )


def get_de_custom_recognizers() -> list[PatternRecognizer]:
    return [
        _email_recognizer(),
        _date_recognizer(),
        _bic_recognizer(),
        _steuer_id_recognizer(),
        _sozialversicherungsnummer_recognizer(),
        _address_recognizer(),
    ]
