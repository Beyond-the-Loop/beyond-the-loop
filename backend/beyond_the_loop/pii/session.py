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
from typing import Any, Dict, Iterable, List, Optional, Protocol, Set, Tuple

from beyond_the_loop.pii.service import PiiSpan, PrivacyFilterService
from beyond_the_loop.prompts import PII_PLACEHOLDER_NOTE

log = logging.getLogger(__name__)


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


_PLACEHOLDER_LABEL: Dict[str, str] = {
    "private_person": "PERSON",
    "private_address": "ADDRESS",
    "private_email": "EMAIL",
    "private_phone": "PHONE",
    "private_url": "URL",
    "private_date": "DATE",
    "account_number": "ACCOUNT",
    "secret": "SECRET",
    "manual": "MANUAL",
}

class PIIStorage(Protocol):
    def load(self, chat_id: str) -> Optional[dict]: ...
    def save(self, chat_id: str, data: dict) -> None: ...


class DBPIIStorage:
    def load(self, chat_id: str) -> Optional[dict]:
        from beyond_the_loop.models.chats import Chats
        return Chats.get_pii_session(chat_id)

    def save(self, chat_id: str, data: dict) -> None:
        from beyond_the_loop.models.chats import Chats
        Chats.save_pii_session(chat_id, data)


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
        service: Optional[PrivacyFilterService] = None,
    ) -> None:
        self.chat_id = chat_id
        self.storage = storage if storage is not None else get_default_storage()
        self.service = service if service is not None else PrivacyFilterService.instance()

        data = self.storage.load(chat_id) or {}
        self.forward: Dict[str, str] = data.get("forward", {})
        self.reverse: Dict[str, str] = data.get("reverse", {})
        self.counters: Dict[str, int] = data.get("counters", {})
        # sources tracks where each `original` was seen across the chat.
        # JSON only supports lists, not sets — convert on load.
        self.sources: Dict[str, Set[str]] = {
            k: set(v) for k, v in data.get("sources", {}).items()
        }
        # Cache of analyze results keyed by raw text. Re-anonymizing the same
        # prior-turn message on every send (anonymize_messages iterates the
        # whole history) would otherwise rerun the transformer on text we've
        # already analyzed — the dominant cost. Cache values are plain dicts
        # so they round-trip through JSON storage; spans are rebuilt as
        # PiiSpan on read.
        self.analyze_cache: Dict[str, List[Dict[str, Any]]] = data.get(
            "analyze_cache", {}
        )

    def save(self) -> None:
        self.storage.save(
            self.chat_id,
            {
                "forward": self.forward,
                "reverse": self.reverse,
                "counters": self.counters,
                "sources": {k: sorted(v) for k, v in self.sources.items()},
                "analyze_cache": self.analyze_cache,
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
    ) -> Tuple[str, List[str]]:
        """Anonymize PII in `text` and tag every detected entity with `source`.

        Returns (output, released_used). `released_used` is the subset of
        `released` that actually appeared in `text` as a detected entity —
        the frontend uses it to surface the "released" badge / list.

        `source` flows into self.sources so the frontend can later show which
        text region (typed prompt vs file vs RAG chunk) contributed each
        entity. Defaults to "prompt" for backwards-compat with callers that
        haven't been updated.
        """
        if not text or not text.strip():
            return text, []

        released_set: Set[str] = set(released) if released else set()

        ner_spans = self._analyze_cached(text)
        manual_spans = self._find_manual_entity_spans(text)
        spans = self._merge_spans(ner_spans, manual_spans)

        # Replace right-to-left so earlier offsets stay valid.
        out = text
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

        # Second pass: NER on long documents drops repeats due to chunked
        # transformer inference, so a name caught once can leak elsewhere.
        # Substitute every remaining verbatim occurrence of an already-known
        # original.
        out, _ = self._sweep_known(out, source, released_set)
        return out, released_used

    def register_manual(self, text: str) -> str:
        """Register a manually selected entity and return its placeholder.

        Unlike anonymize(), this does NOT run NER — the user explicitly chose
        this text. The placeholder is created immediately and _sweep_known()
        will replace every occurrence when anonymize_messages() runs after.
        """
        if not text or not text.strip():
            return text
        return self._get_or_create_placeholder("manual", text)

    def replace_known(
        self,
        text: str,
        released: Optional[Iterable[str]] = None,
        source: str = "prompt",
    ) -> Tuple[str, List[str]]:
        """Sweep-only: replace already-known entities, do NOT detect new ones.

        Used for past assistant messages in the chat history — model-generated
        text isn't user PII, so seeding new placeholders for it has no privacy
        benefit and just wastes tokens / pollutes the sidebar. But user PII
        that the model echoed back must stay anonymized so downstream turns
        see the same placeholder the user-side anonymization established.

        Return shape matches `anonymize` so callers can dispatch by role
        without branching on tuple arity. `released_used` is always [] here
        because this path does not look at released entities — it just
        rewrites known originals.
        """
        if not text:
            return text, []
        released_set: Set[str] = set(released) if released else set()
        out, _ = self._sweep_known(text, source, released_set)
        return out, []

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

    def _find_manual_entity_spans(self, text: str) -> List[PiiSpan]:
        """Find all positions of registered manual entities in text."""
        spans = []
        for original, placeholder in self.forward.items():
            if not placeholder.startswith("[[MANUAL_"):
                continue
            idx = 0
            while True:
                pos = text.find(original, idx)
                if pos == -1:
                    break
                spans.append(PiiSpan("manual", pos, pos + len(original), 1.0))
                idx = pos + 1
        return spans

    @staticmethod
    def _merge_spans(ner_spans: List[PiiSpan], manual_spans: List[PiiSpan]) -> List[PiiSpan]:
        """Merge NER and manual spans; manual takes priority on overlap."""
        result: List[PiiSpan] = list(manual_spans)
        for span in ner_spans:
            if not any(s.start < span.end and span.start < s.end for s in result):
                result.append(span)
        return sorted(result, key=lambda s: s.start)

    def _analyze_cached(self, text: str) -> List[PiiSpan]:
        cached = self.analyze_cache.get(text)
        if cached is not None:
            return [
                PiiSpan(
                    entity_type=s["entity_type"],
                    start=s["start"],
                    end=s["end"],
                    score=s["score"],
                )
                for s in cached
            ]
        spans = self.service.analyze(text)
        self.analyze_cache[text] = [
            {
                "entity_type": s.entity_type,
                "start": int(s.start),
                "end": int(s.end),
                "score": float(s.score),
            }
            for s in spans
        ]
        return spans

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
    def calculate_shifted_index(
        self,
        anonymized_text: str,
        anon_end_index: int,
        utf8: bool = False,
    ) -> int:
        if not self.forward or not anonymized_text:
            return anon_end_index

        if utf8:
            work = anonymized_text.encode("utf-8")
            enc = lambda s: s.encode("utf-8")
        else:
            work = anonymized_text
            enc = lambda s: s

        shift = 0
        for original, placeholder in self.forward.items():
            orig_enc = enc(original)
            ph_enc   = enc(placeholder)
            delta = len(orig_enc) - len(ph_enc)
            if delta == 0:
                continue
            search_from = 0
            while True:
                idx = work.find(ph_enc, search_from)
                if idx == -1 or idx >= anon_end_index:
                    break
                shift += delta
                search_from = idx + len(ph_enc)
        return anon_end_index + shift

def anonymize_messages(
    messages: List[dict],
    session: PIISession,
    released: Optional[Iterable[str]] = None,
    source: str = "prompt",
) -> List[str]:
    """In-place anonymize the 'content' of every user/assistant chat message.

    Returns `released_used` — the subset of `released` originals that actually
    appeared in at least one message. The caller surfaces this to the
    frontend as the per-message released list.

    System messages are skipped: they're platform-controlled (default prompts,
    assistant configs) and contain no user PII. RAG and extracted document
    content are anonymized via the dedicated hooks before they're ever merged
    into a system message, so skipping system role here is safe.

    Handles both string content and OpenAI-style multimodal content
    (list of parts); only text parts are touched, image parts pass through.
    """
    released_list = list(released) if released else []
    released_used: List[str] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue
        # Past assistant messages: only re-anonymize already-known user PII.
        # Model-generated entities (URLs, names the model invented) aren't user
        # data — seeding placeholders for them wastes tokens and confuses the
        # sidebar with entries the user never typed.
        anonymize_fn = session.anonymize if role == "user" else session.replace_known
        content = msg.get("content")
        if isinstance(content, str):
            new_content, ru = anonymize_fn(content, released_list, source=source)
            msg["content"] = new_content
            released_used.extend(ru)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    new_text, ru = anonymize_fn(part.get("text", ""), released_list, source=source)
                    part["text"] = new_text
                    released_used.extend(ru)
    return released_used


def anonymize_filename(name: str, session: Optional[PIISession]) -> str:
    """Replace PII in a filename, sharing placeholders with the chat session.

    Filenames like "Vertrag_Mueller_Hans.pdf" leak PII when forwarded to
    intent-decision LLMs or external upload APIs. No-op when session is None
    (filter inactive) or name is empty.
    """
    if session is None or not name:
        return name
    out, _ = session.anonymize(name)
    return out