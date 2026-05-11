"""
PresidioService — Singleton wrapping a Presidio AnalyzerEngine that uses a
HuggingFace transformer for German NER.

NER is done by `Davlan/xlm-roberta-base-ner-hrl` via Presidio's
TransformersNlpEngine. spaCy (`de_core_news_sm`) is kept only as the
tokenizer/lemmatizer backbone — its statistical NER is disabled.

XLM-R is preferred over the cased mBERT version: SentencePiece tokenisation
makes the same Subword-Pieces appear regardless of casing, so lowercase
proper nouns ("anna", "hamburg") still produce useful embeddings.

Initial load (first call to `instance()`) downloads/loads the transformer
model and takes ~10-30s. Call `instance()` once at app startup to warm up.
Thread-safe: the underlying AnalyzerEngine is safe to call concurrently.
"""
from __future__ import annotations

import copy
import logging
import re
import threading
from typing import Iterable, List, Optional

# Drop transformers' INFO logs ("Device set to use cpu" etc.) but keep WARNING+.
import transformers
transformers.logging.set_verbosity_warning()

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    IbanRecognizer,
    IpRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
    UrlRecognizer,
)

from beyond_the_loop.pii.recognizers import get_de_custom_recognizers

log = logging.getLogger(__name__)

LANGUAGE = "de"
# spaCy is only the tokenizer here — its NER is disabled by TransformersNlpEngine.
# `sm` is sufficient and ~30x smaller than `lg`.
SPACY_MODEL = "de_core_news_sm"
NER_MODEL = "Davlan/xlm-roberta-base-ner-hrl"

# DATE_TIME and BIC_CODE are scoped through custom recognizers rather than
# Presidio's broad default.
SUPPORTED_ENTITIES: List[str] = [
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IBAN_CODE",
    "BIC_CODE",
    "IP_ADDRESS",
    "URL",
    "DATE_TIME",
    "DE_STEUER_ID",
    "DE_SOZIALVERSICHERUNGSNUMMER",
    "DE_ADDRESS",
]

# Maps the Davlan model's CoNLL-style output labels onto Presidio entity types.
# Entries not in SUPPORTED_ENTITIES (e.g. MISC) get filtered out by the engine.
_NER_MODEL_CONFIGURATION = {
    "model_to_presidio_entity_mapping": {
        "PER": "PERSON",
        "LOC": "LOCATION",
        "ORG": "ORGANIZATION",
        "MISC": "MISC",
        "DATE": "DATE_TIME",
    },
    "labels_to_ignore": [],
    "low_confidence_score_multiplier": 0.4,
    "low_score_entity_names": [],
    "aggregation_strategy": "simple",
    "stride": 14,
    "alignment_mode": "expand",
    "default_score": 0.85,
}


class PresidioService:
    _instance: Optional["PresidioService"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "transformers",
                "models": [
                    {
                        "lang_code": LANGUAGE,
                        "model_name": {
                            "spacy": SPACY_MODEL,
                            "transformers": NER_MODEL,
                        },
                    }
                ],
                "ner_model_configuration": _NER_MODEL_CONFIGURATION,
            }
        ).create_engine()

        registry = RecognizerRegistry(supported_languages=[LANGUAGE])

        # Pattern-based recognizers bound to "de". Regex is language-agnostic;
        # predefined context strings are English so context boost won't fire
        # on German text, but base detection still works.
        registry.add_recognizer(CreditCardRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(IbanRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(IpRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(UrlRecognizer(supported_language=LANGUAGE))
        registry.add_recognizer(
            PhoneRecognizer(
                supported_language=LANGUAGE,
                supported_regions=("DE", "AT", "CH", "GB", "US", "FR", "ES"),
            )
        )

        # SpacyRecognizer is just the bridge that surfaces NER results from
        # nlp_artifacts.entities — works identically with TransformersNlpEngine
        # because the engine populates the same artifact shape, with labels
        # already mapped to Presidio entity types via _NER_MODEL_CONFIGURATION.
        registry.add_recognizer(
            SpacyRecognizer(
                supported_language=LANGUAGE,
                supported_entities=["PERSON", "LOCATION", "ORGANIZATION"],
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
                        "Initializing PresidioService (loading %s + spaCy %s)",
                        NER_MODEL,
                        SPACY_MODEL,
                    )
                    cls._instance = cls()
                    log.info("PresidioService initialized")
        return cls._instance

    def analyze(
        self,
        text: str,
        entities: Optional[Iterable[str]] = None,
    ) -> List[RecognizerResult]:
        if not text or not text.strip():
            return []
        ents = list(entities) if entities is not None else SUPPORTED_ENTITIES
        base = self.analyzer.analyze(text=text, entities=ents, language=LANGUAGE)

        # Cased NER barely fires on all-lowercase text ("anna", "hamburg").
        # Re-run NER on a title-cased copy and merge in PERSON/LOCATION hits
        # the original pass missed. str.title() preserves character offsets
        # 1:1, so spans from the second pass map straight back onto `text`.
        # Restricted to all-lowercase input to avoid false positives in
        # mixed-case text where the title-cased version turns ordinary words
        # ("ist", "in") into name-like tokens.
        if any(c.isalpha() for c in text) and not any(c.isupper() for c in text):
            ner_only = [e for e in ("PERSON", "LOCATION", "ORGANIZATION") if e in ents]
            if ner_only:
                extra = self.analyzer.analyze(
                    text=text.title(),
                    entities=ner_only,
                    language=LANGUAGE,
                )
                base.extend(extra)

        # Transformer NER occasionally produces spans whose source slice is
        # whitespace-only (subword tokenizer alignment artifacts). Drop them
        # before downstream consumers see them, otherwise they show up as
        # empty chips in the sidebar and inflate the entity count.
        base = [r for r in base if text[r.start : r.end].strip()]

        return _resolve_overlaps(_extend_truncated_person_spans(text, base))


_TRAILING_NAME_WORD = re.compile(r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{1,30}")


def _extend_truncated_person_spans(
    text: str,
    spans: List[RecognizerResult],
) -> List[RecognizerResult]:
    """Extend PERSON spans by one trailing capitalized word.

    Subword tokenizer artifacts (umlauts, hyphens) sometimes split "Thore
    Dücker" into two transformer predictions. The first one aligns to spaCy's
    "Thore" token via `expand`; the second ("e Dücker") then overlaps the
    already-aligned first and gets dropped — the surname leaks. If a PERSON
    span is followed by exactly one space and a capitalised, German-style
    word that isn't already inside another span, extend the span to include
    it so the full name ends up as one placeholder.
    """
    if not spans:
        return spans
    out: List[RecognizerResult] = []
    for span in spans:
        if (
            span.entity_type != "PERSON"
            or span.end >= len(text)
            or text[span.end] != " "
        ):
            out.append(span)
            continue
        match = _TRAILING_NAME_WORD.match(text, span.end + 1)
        if not match:
            out.append(span)
            continue
        new_end = match.end()
        if any(
            span.end < other.start < new_end
            for other in spans
            if other is not span
        ):
            out.append(span)
            continue
        extended = copy.copy(span)
        extended.end = new_end
        out.append(extended)
    return out


def _resolve_overlaps(results: List[RecognizerResult]) -> List[RecognizerResult]:
    """Return non-overlapping spans, preferring the longer (more specific) one.

    Sort by span length descending, with score as tiebreaker. Processing the
    longest span first means that when a shorter span overlaps with an
    already-kept one, it gets dropped — so a DE_ADDRESS hit on "Hauptstraße 12"
    wins over a LOCATION hit on "Hauptstraße" even though the NER score for
    LOCATION is higher. Equal-length spans fall back to score.
    """
    by_priority = sorted(results, key=lambda r: (-(r.end - r.start), -r.score))
    kept: List[RecognizerResult] = []
    for r in by_priority:
        overlaps = any(
            not (r.end <= k.start or r.start >= k.end) for k in kept
        )
        if not overlaps:
            kept.append(r)
    return sorted(kept, key=lambda r: r.start)
