"""
PrivacyFilterService — Singleton talking to the openai/privacy-filter
inference endpoint (Cloud Run).

The remote container runs a single forward pass through a sparse MoE
transformer (1.5B total / 50M active params) and returns raw token-level
predictions with BIOES tags (B-/I-/E-/S-/O). HuggingFace's `aggregation_strategy`
only understands BIO and fragments BIOES output, so the container ships raw
tokens and we decode BIOES ourselves below.

Supported entity categories:
  private_person, private_address, private_email, private_phone,
  private_url, private_date, account_number, secret

Configure the endpoint via the `PII_INFERENCE_URL` env var.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import List, Optional

from .inference_client import PiiInferenceClient

# Spans below this confidence score are dropped to reduce false positives
# (e.g. random keyboard-mash strings classified as "secret" by the model).
# Override via PII_MIN_SCORE env var.
MIN_PII_SCORE: float = float(os.environ.get("PII_MIN_SCORE", "0.85"))

log = logging.getLogger(__name__)

SUPPORTED_ENTITIES: List[str] = [
    "private_person",
    "private_address",
    "private_email",
    "private_phone",
    "private_url",
    "private_date",
    "account_number",
    "secret",
]


@dataclass
class PiiSpan:
    entity_type: str
    start: int
    end: int
    score: float


class PrivacyFilterService:
    _instance: Optional["PrivacyFilterService"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._client = PiiInferenceClient()

    @classmethod
    def instance(cls) -> "PrivacyFilterService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    log.info("Initializing PrivacyFilterService")
                    cls._instance = cls()
                    log.info("PrivacyFilterService ready")
        return cls._instance

    def analyze(self, text: str) -> List[PiiSpan]:
        if not text or not text.strip():
            return []

        raw = self._client.predict([text])[0]
        spans = self._decode_bioes(raw)
        result = []
        for s in spans:
            trimmed = self._trim_whitespace(s, text)
            if trimmed is None:
                continue
            span_text = text[trimmed.start:trimmed.end]
            if not self._has_alphanumeric(span_text):
                continue
            kept = trimmed.score >= MIN_PII_SCORE
            print(
                f"[PII] type={trimmed.entity_type} score={trimmed.score:.4f} "
                f"text={span_text!r} threshold={MIN_PII_SCORE:.2f} kept={kept}",
                flush=True,
            )
            if kept:
                result.append(trimmed)
        return result

    @staticmethod
    def _has_alphanumeric(s: str) -> bool:
        return any(c.isalnum() for c in s)

    @staticmethod
    def _trim_whitespace(span: "PiiSpan", text: str) -> Optional["PiiSpan"]:
        # BPE tokenizers prefix word-initial subwords with a leading-space
        # marker (Ġ), and the model often labels that marker as part of the
        # entity span. Left intact, the placeholder swallows the space before
        # the original — e.g. "Hallo Max" → "Hallo[[PERSON_1]]". Trim both
        # ends so the span covers the entity text only.
        raw = text[span.start:span.end]
        left = len(raw) - len(raw.lstrip())
        right = len(raw) - len(raw.rstrip())
        new_start = span.start + left
        new_end = span.end - right
        if new_start >= new_end:
            return None
        return PiiSpan(
            entity_type=span.entity_type,
            start=new_start,
            end=new_end,
            score=span.score,
        )

    @staticmethod
    def _decode_bioes(tokens) -> List[PiiSpan]:
        spans: List[PiiSpan] = []
        current: Optional[dict] = None

        def flush():
            nonlocal current
            if current is not None:
                spans.append(
                    PiiSpan(
                        entity_type=current["type"],
                        start=current["start"],
                        end=current["end"],
                        score=sum(current["scores"]) / len(current["scores"]),
                    )
                )
                current = None

        for tok in tokens:
            label = tok.get("entity") or tok.get("entity_group") or "O"
            start = int(tok["start"])
            end = int(tok["end"])
            score = float(tok["score"])

            if label == "O" or "-" not in label:
                flush()
                continue

            prefix, etype = label.split("-", 1)

            if prefix == "S":
                flush()
                spans.append(PiiSpan(etype, start, end, score))
            elif prefix == "B":
                flush()
                current = {"type": etype, "start": start, "end": end, "scores": [score]}
            elif prefix == "I":
                if current is not None and current["type"] == etype:
                    current["end"] = end
                    current["scores"].append(score)
                else:
                    flush()
                    current = {"type": etype, "start": start, "end": end, "scores": [score]}
            elif prefix == "E":
                if current is not None and current["type"] == etype:
                    current["end"] = end
                    current["scores"].append(score)
                    flush()
                else:
                    flush()
                    spans.append(PiiSpan(etype, start, end, score))
            else:
                flush()

        flush()
        return spans
