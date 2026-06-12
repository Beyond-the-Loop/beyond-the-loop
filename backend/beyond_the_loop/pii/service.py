"""
PrivacyFilterService — Singleton wrapping the openai/privacy-filter model.

Single forward pass through a sparse MoE transformer (1.5B total / 50M active
parameters) with a constrained Viterbi decoder for coherent span boundaries.
No spaCy, no Presidio, no double-pass for lowercase text.

Supported entity categories:
  private_person, private_address, private_email, private_phone,
  private_url, private_date, account_number, secret

Initial load (first call to `instance()`) downloads the model on cache miss;
subsequent starts load from the HuggingFace cache directory. Call `instance()`
once at app startup to warm up.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import List, Optional

from transformers import pipeline

log = logging.getLogger(__name__)

MODEL_NAME = "openai/privacy-filter"

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
        self._pipe = pipeline(
            "token-classification",
            model=MODEL_NAME,
            aggregation_strategy="simple",
            device="cpu",
        )

    @classmethod
    def instance(cls) -> "PrivacyFilterService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    log.info("Initializing PrivacyFilterService (%s)", MODEL_NAME)
                    cls._instance = cls()
                    log.info("PrivacyFilterService ready")
        return cls._instance

    def analyze(self, text: str) -> List[PiiSpan]:
        if not text or not text.strip():
            return []

        raw = self._pipe(text)

        return [
            PiiSpan(
                entity_type=r["entity_group"],
                start=int(r["start"]),
                end=int(r["end"]),
                score=float(r["score"]),
            )
            for r in raw
            if text[r["start"]: r["end"]].strip()
        ]
