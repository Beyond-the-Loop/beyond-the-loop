"""
PIISession — per-chat bidirectional mapping between PII originals and placeholders.

Loads state from Redis at construction, persists via explicit save().
Placeholder format: [[TYPE_N]] where TYPE is a short entity label and N is a
per-type counter within the session. Counters start at 1.

Concurrency note: two concurrent requests on the same chat can race on the
counter and last-write-wins would corrupt the reverse map. Within a single
chat this is rare (messages are sequential from the user). If it becomes a
problem in production, switch to hash-based placeholders (sha256 of original)
or add a Redis-side lock.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Protocol

import redis

from beyond_the_loop.pii.service import PresidioService

log = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days, refreshed on every save

PII_SYSTEM_PROMPT = (
    "Wichtig: In den folgenden Nachrichten wurden personenbezogene Daten "
    "durch Platzhalter der Form [[TYP_N]] ersetzt (z.B. [[PERSON_1]], "
    "[[EMAIL_1]], [[IBAN_1]], [[ADDRESS_1]]). Übernimm diese Platzhalter in "
    "deiner Antwort exakt und unverändert, wenn du dich auf die entsprechenden "
    "Daten beziehst. Übersetze, paraphrasiere oder modifiziere sie nicht."
)


def is_pii_filter_enabled(company_id) -> bool:
    """Feature-flag check. Default is ON: unset → True, explicit False → False."""
    from beyond_the_loop.config import get_config_value

    value = get_config_value("privacy.pii_filter_enabled", company_id)
    return True if value is None else bool(value)

# Map Presidio entity type → short placeholder label. Shorter is friendlier
# for the LLM to preserve verbatim.
_PLACEHOLDER_LABEL: Dict[str, str] = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CARD",
    "IBAN_CODE": "IBAN",
    "IP_ADDRESS": "IP",
    "URL": "URL",
    "DE_STEUER_ID": "STEUERID",
    "DE_SOZIALVERSICHERUNGSNUMMER": "SVNR",
    "DE_ADDRESS": "ADDRESS",
}


class PIIStorage(Protocol):
    def load(self, chat_id: str) -> Optional[dict]: ...
    def save(self, chat_id: str, data: dict) -> None: ...


class RedisPIIStorage:
    """Persists session state as a single JSON blob per chat_id with TTL."""

    def __init__(self, redis_url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self.ttl = ttl_seconds

    @staticmethod
    def _key(chat_id: str) -> str:
        return f"pii_session:{chat_id}"

    def load(self, chat_id: str) -> Optional[dict]:
        raw = self.redis.get(self._key(chat_id))
        return json.loads(raw) if raw else None

    def save(self, chat_id: str, data: dict) -> None:
        self.redis.set(self._key(chat_id), json.dumps(data), ex=self.ttl)


class InMemoryPIIStorage:
    """For tests and local ephemeral use."""

    def __init__(self) -> None:
        self._data: Dict[str, dict] = {}

    def load(self, chat_id: str) -> Optional[dict]:
        return self._data.get(chat_id)

    def save(self, chat_id: str, data: dict) -> None:
        self._data[chat_id] = data


_default_storage: Optional[PIIStorage] = None


def get_default_storage() -> PIIStorage:
    global _default_storage
    if _default_storage is None:
        from open_webui.env import REDIS_URL

        _default_storage = RedisPIIStorage(REDIS_URL)
    return _default_storage


class PIISession:
    def __init__(
        self,
        chat_id: str,
        storage: Optional[PIIStorage] = None,
        presidio: Optional[PresidioService] = None,
    ) -> None:
        self.chat_id = chat_id
        self.storage = storage if storage is not None else get_default_storage()
        self.presidio = presidio if presidio is not None else PresidioService.instance()

        data = self.storage.load(chat_id) or {}
        self.forward: Dict[str, str] = data.get("forward", {})
        self.reverse: Dict[str, str] = data.get("reverse", {})
        self.counters: Dict[str, int] = data.get("counters", {})

    def save(self) -> None:
        self.storage.save(
            self.chat_id,
            {
                "forward": self.forward,
                "reverse": self.reverse,
                "counters": self.counters,
            },
        )

    def anonymize(self, text: str) -> str:
        if not text or not text.strip():
            return text

        results = self.presidio.analyze(text)
        if not results:
            return text

        spans = self._resolve_overlaps(results)
        if not spans:
            return text

        # Replace right-to-left so earlier offsets stay valid.
        out = text
        for r in reversed(spans):
            original = text[r.start : r.end]
            placeholder = self._get_or_create_placeholder(r.entity_type, original)
            out = out[: r.start] + placeholder + out[r.end :]
        return out

    def deanonymize(self, text: str) -> str:
        if not text or not self.reverse:
            return text
        # Sort by placeholder length descending so longer labels get replaced
        # before any that might be a prefix substring.
        for placeholder in sorted(self.reverse.keys(), key=len, reverse=True):
            text = text.replace(placeholder, self.reverse[placeholder])
        return text

    def streaming_deanonymizer(self):
        """Return a StreamingDeanonymizer bound to this session's reverse map."""
        from beyond_the_loop.pii.streaming import StreamingDeanonymizer

        return StreamingDeanonymizer(self.reverse)

    def _get_or_create_placeholder(self, entity_type: str, original: str) -> str:
        existing = self.forward.get(original)
        if existing is not None:
            return existing

        label = _PLACEHOLDER_LABEL.get(entity_type, entity_type)
        self.counters[label] = self.counters.get(label, 0) + 1
        placeholder = f"[[{label}_{self.counters[label]}]]"
        self.forward[original] = placeholder
        self.reverse[placeholder] = original
        return placeholder

    @staticmethod
    def _resolve_overlaps(results: List) -> List:
        """Return non-overlapping spans, preferring highest score on conflict."""
        by_score = sorted(results, key=lambda r: -r.score)
        kept: List = []
        for r in by_score:
            overlaps = any(
                not (r.end <= k.start or r.start >= k.end) for k in kept
            )
            if not overlaps:
                kept.append(r)
        return sorted(kept, key=lambda r: r.start)


def anonymize_messages(messages: List[dict], session: PIISession) -> None:
    """In-place anonymize the 'content' of every chat message.

    Handles both string content and OpenAI-style multimodal content
    (list of parts); only text parts are touched, image parts pass through.
    """
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = session.anonymize(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    part["text"] = session.anonymize(part.get("text", ""))
