"""
PIISession — per-chat bidirectional mapping between PII originals and placeholders.

State is persisted in the chat row's `chat` JSON column under the
`pii_session` key. Loads at construction, writes via explicit save().
Placeholder format: [[TYPE_N]] where TYPE is a short entity label and N is a
per-type counter within the session. Counters start at 1.

Concurrency note: two concurrent requests on the same chat can race on the
counter and last-write-wins would corrupt the reverse map. Within a single
chat this is rare (messages are sequential from the user). If it becomes a
problem in production, switch to hash-based placeholders (sha256 of original)
or add a row-level lock.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Protocol, Set, Tuple

from sqlalchemy.orm.attributes import flag_modified

from beyond_the_loop.pii.service import PresidioService
from beyond_the_loop.prompts import PII_PLACEHOLDER_NOTE

log = logging.getLogger(__name__)

PII_SESSION_KEY = "pii_session"


def pii_note_prefix(pii_active: bool) -> str:
    """Prepend to a system prompt when the chat runs under PII anonymization."""
    return PII_PLACEHOLDER_NOTE if pii_active else ""


def is_pii_filter_enabled(company_id) -> bool:
    """Feature-flag check. Default is OFF: unset → False, explicit True → True.

    Companies must opt in via privacy.pii_filter_enabled = True (set by
    admins through the company settings UI).
    """
    from beyond_the_loop.config import get_config_value

    value = get_config_value("privacy.pii_filter_enabled", company_id)
    return False if value is None else bool(value)

# Map Presidio entity type → short placeholder label. Shorter is friendlier
# for the LLM to preserve verbatim.
_PLACEHOLDER_LABEL: Dict[str, str] = {
    "PERSON": "PERSON",
    "LOCATION": "LOCATION",
    "ORGANIZATION": "ORG",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "DATE_TIME": "DATUM",
    "CREDIT_CARD": "CARD",
    "IBAN_CODE": "IBAN",
    "BIC_CODE": "BIC",
    "IP_ADDRESS": "IP",
    "URL": "URL",
    "DE_STEUER_ID": "STEUERID",
    "DE_SOZIALVERSICHERUNGSNUMMER": "SVNR",
    "DE_ADDRESS": "ADDRESS",
}


class PIIStorage(Protocol):
    def load(self, chat_id: str) -> Optional[dict]: ...
    def save(self, chat_id: str, data: dict) -> None: ...


class DBPIIStorage:
    """Persists session state in the chat row's `chat` JSON under `pii_session`.

    Lives for the lifetime of the chat — no TTL. If the chat row does not
    yet exist (first message before /chats/new), save is a no-op and the
    next request reloads an empty mapping; the deanonymizer would then leave
    placeholders in the response. In practice the frontend creates the chat
    row before calling the chat completion endpoint, so this is a guard,
    not a hot path.
    """

    def load(self, chat_id: str) -> Optional[dict]:
        from open_webui.internal.db import get_db
        from beyond_the_loop.models.chats import Chat

        with get_db() as db:
            chat_item = db.get(Chat, chat_id)
            if chat_item is None or not isinstance(chat_item.chat, dict):
                return None
            return chat_item.chat.get(PII_SESSION_KEY)

    def save(self, chat_id: str, data: dict) -> None:
        from open_webui.internal.db import get_db
        from beyond_the_loop.models.chats import Chat

        with get_db() as db:
            chat_item = db.get(Chat, chat_id)
            if chat_item is None:
                log.warning(
                    "[pii] cannot persist session: chat row %s not found", chat_id
                )
                return
            if not isinstance(chat_item.chat, dict):
                chat_item.chat = {}
            chat_item.chat[PII_SESSION_KEY] = data
            flag_modified(chat_item, "chat")
            db.commit()


class InMemoryPIIStorage:
    """For tests."""

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
        _default_storage = DBPIIStorage()
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
        # sources tracks where each `original` was seen across the chat.
        # JSON only supports lists, not sets — convert on load.
        self.sources: Dict[str, Set[str]] = {
            k: set(v) for k, v in data.get("sources", {}).items()
        }

    def save(self) -> None:
        self.storage.save(
            self.chat_id,
            {
                "forward": self.forward,
                "reverse": self.reverse,
                "counters": self.counters,
                "sources": {k: sorted(v) for k, v in self.sources.items()},
            },
        )

    def sources_serialized(self) -> Dict[str, List[str]]:
        """Sources as a JSON-friendly {original: [source, ...]} map."""
        return {k: sorted(v) for k, v in self.sources.items()}

    def anonymize(
        self,
        text: str,
        released: Optional[Iterable[str]] = None,
        source: str = "prompt",
    ) -> Tuple[str, int, int, List[str]]:
        """Anonymize PII in `text` and tag every detected entity with `source`.

        Returns (output, total_detected, anonymized, released_used).

        `source` flows into self.sources so the frontend can later show which
        text region (typed prompt vs file vs RAG chunk) contributed each
        entity. Defaults to "prompt" for backwards-compat with callers that
        haven't been updated.

        - total_detected: spans Presidio kept after overlap resolution
        - anonymized: spans actually replaced (i.e. not in `released`)
        - released_used: original strings that WERE skipped (subset of
          `released` that actually appeared in `text` as a detected entity).
        """
        if not text or not text.strip():
            return text, 0, 0, []

        released_set: Set[str] = set(released) if released else set()

        spans = self.presidio.analyze(text)

        # Replace right-to-left so earlier offsets stay valid.
        out = text
        anonymized_count = 0
        released_used: List[str] = []
        for r in reversed(spans):
            original = text[r.start : r.end]
            # Track source even for released entities — they were still seen
            # from this surface, frontend just won't display them under the
            # protected list (they go to the released bucket instead).
            self.sources.setdefault(original, set()).add(source)
            if original in released_set:
                released_used.append(original)
                continue
            placeholder = self._get_or_create_placeholder(r.entity_type, original)
            out = out[: r.start] + placeholder + out[r.end :]
            anonymized_count += 1

        # Second pass: NER on long documents drops repeats due to chunked
        # transformer inference, so a name caught once can leak elsewhere.
        # Substitute every remaining verbatim occurrence of an already-known
        # original.
        out, sweep_count = self._sweep_known(out, source, released_set)
        return out, len(spans) + sweep_count, anonymized_count + sweep_count, released_used

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

    def _sweep_known(
        self,
        text: str,
        source: str,
        released_set: Set[str],
    ) -> Tuple[str, int]:
        # Released originals stay verbatim by design — exclude them from the sweep.
        originals = sorted(
            (o for o in self.forward if o and o not in released_set),
            key=len,
            reverse=True,
        )
        if not originals:
            return text, 0

        pattern = re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(o) for o in originals) + r")(?!\w)"
        )

        count = 0

        def repl(match: re.Match) -> str:
            nonlocal count
            original = match.group(0)
            self.sources.setdefault(original, set()).add(source)
            count += 1
            return self.forward[original]

        return pattern.sub(repl, text), count

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


def anonymize_messages(
    messages: List[dict],
    session: PIISession,
    released: Optional[Iterable[str]] = None,
    source: str = "prompt",
) -> Tuple[int, int, List[str]]:
    """In-place anonymize the 'content' of every user/assistant chat message.

    Returns (total_detected, anonymized, released_used) summed across all
    touched messages so the caller can derive a per-request status (full /
    partial / none) and report which user-released entities actually appeared.

    System messages are skipped: they're platform-controlled (default prompts,
    assistant configs) and contain no user PII, but their formatting/capability
    descriptions cause heavy false positives in the German spaCy NER (e.g.
    "Blockquotes", "Bolding", "slides"). RAG and extracted document content
    are anonymized via the dedicated hooks before they're ever merged into a
    system message, so skipping system role here is safe.

    Handles both string content and OpenAI-style multimodal content
    (list of parts); only text parts are touched, image parts pass through.
    """
    released_list = list(released) if released else []
    total = 0
    anonymized = 0
    released_used: List[str] = []
    for msg in messages:
        if msg.get("role") == "system":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            new_content, t, a, ru = session.anonymize(content, released_list, source=source)
            msg["content"] = new_content
            total += t
            anonymized += a
            released_used.extend(ru)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    new_text, t, a, ru = session.anonymize(part.get("text", ""), released_list, source=source)
                    part["text"] = new_text
                    total += t
                    anonymized += a
                    released_used.extend(ru)
    return total, anonymized, released_used


def anonymize_filename(name: str, session: Optional[PIISession]) -> str:
    """Replace PII in a filename, sharing placeholders with the chat session.

    Filenames like "Vertrag_Mueller_Hans.pdf" leak PII when forwarded to
    intent-decision LLMs or external upload APIs. No-op when session is None
    (filter inactive) or name is empty.
    """
    if session is None or not name:
        return name
    out, _, _, _ = session.anonymize(name)
    return out
