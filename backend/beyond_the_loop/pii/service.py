"""
PresidioService — Singleton wrapping a spaCy-backed Presidio analyzer
configured for German PII detection.

Initial load (spaCy de_core_news_lg) takes ~2-5s; call `instance()` once at
app startup to warm up. Thread-safe: the underlying AnalyzerEngine is safe
to call concurrently.
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    IpRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
    UrlRecognizer,
)

from beyond_the_loop.pii.recognizers import get_de_custom_recognizers

log = logging.getLogger(__name__)

LANGUAGE = "de"
SPACY_MODEL = "de_core_news_lg"

# Presidio defaults minus ORGANIZATION (product decision: company names are
# not PII for us) and minus DATE_TIME (high false-positive rate in German
# free text — "Montag", "nächste Woche" etc.).
SUPPORTED_ENTITIES: List[str] = [
    "PERSON",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
    "DE_STEUER_ID",
    "DE_SOZIALVERSICHERUNGSNUMMER",
    "DE_ADDRESS",
]


class PresidioService:
    _instance: Optional["PresidioService"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": LANGUAGE, "model_name": SPACY_MODEL}],
            }
        ).create_engine()

        registry = RecognizerRegistry(supported_languages=[LANGUAGE])

        # Pattern-based recognizers bound to "de". Regex is language-agnostic;
        # predefined context strings are English so context boost won't fire
        # on German text, but base detection still works.
        registry.add_recognizer(EmailRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(CreditCardRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(IbanRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(IpRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(UrlRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(
            PhoneRecognizer(
                supported_language=LANGUAGE,
                supported_regions=("DE",),
            )
        )

        # spaCy NER: only PERSON and LOCATION. ORGANIZATION excluded by product
        # decision; DATE_TIME excluded due to FP rate.
        registry.add_recognizer(
            SpacyRecognizer(
                supported_language=LANGUAGE,
                supported_entities=["PERSON", "LOCATION"],
            )
        )

        for recognizer in get_de_custom_recognizers():
            registry.add_recognizer(recognizer)

        self.analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            registry=registry,
            supported_languages=[LANGUAGE],
        )

    @classmethod
    def instance(cls) -> "PresidioService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    log.info(
                        "Initializing PresidioService (loading spaCy %s)",
                        SPACY_MODEL,
                    )
                    cls._instance = cls()
                    log.info("PresidioService initialized")
        return cls._instance

    def analyze(self, text: str) -> List[RecognizerResult]:
        if not text or not text.strip():
            return []
        return self.analyzer.analyze(
            text=text,
            entities=SUPPORTED_ENTITIES,
            language=LANGUAGE,
        )
