"""
Custom Presidio recognizers for German-specific PII.

Detects:
- DE_STEUER_ID — Steuerliche Identifikationsnummer (11 digits, first digit 1-9)
- DE_SOZIALVERSICHERUNGSNUMMER — 2d + 6d (birthdate) + 1 letter + 3d
- DE_ADDRESS — German street+number and PLZ+city patterns
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


def _steuer_id_recognizer() -> PatternRecognizer:
    patterns = [
        Pattern(
            name="de_steuer_id",
            regex=r"\b[1-9](?:[\s\-]?\d){10}\b",
            score=0.4,
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
        _steuer_id_recognizer(),
        _sozialversicherungsnummer_recognizer(),
        _address_recognizer(),
    ]
