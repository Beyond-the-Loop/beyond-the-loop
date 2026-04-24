"""
StreamingDeanonymizer — buffers incoming LLM chunks and emits deanonymized
text, keeping partial placeholders in the buffer until they can be resolved.

Why buffering: a placeholder like `[[PERSON_1]]` may be split across SSE
chunks ("[[PER" + "SON_1]]"). Replacing per-chunk would leak the half-open
bracket to the client. We only emit up to the last position that cannot
possibly be the start of an unfinished placeholder.

Usage:
    d = StreamingDeanonymizer(reverse_map)
    for chunk in stream:
        client.send(d.feed(chunk))
    client.send(d.flush())  # any remainder at stream end
"""
from __future__ import annotations

from typing import Dict, Tuple


class StreamingDeanonymizer:
    def __init__(self, reverse_map: Dict[str, str]) -> None:
        self.reverse_map = reverse_map
        self.buffer = ""
        # Precompute sorted placeholders once — longest-first avoids a short
        # placeholder matching a prefix of a longer one (e.g. PERSON_1 vs
        # PERSON_11).
        self._sorted_placeholders = sorted(
            reverse_map.keys(), key=len, reverse=True
        )

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self.buffer += chunk
        safe, self.buffer = self._safe_split(self.buffer)
        return self._replace(safe)

    def flush(self) -> str:
        remaining = self.buffer
        self.buffer = ""
        return self._replace(remaining)

    def _replace(self, text: str) -> str:
        if not text or not self.reverse_map:
            return text
        for placeholder in self._sorted_placeholders:
            if placeholder in text:
                text = text.replace(placeholder, self.reverse_map[placeholder])
        return text

    @staticmethod
    def _safe_split(buffer: str) -> Tuple[str, str]:
        """Split buffer into (safe_to_emit, keep_for_next_chunk).

        `keep_for_next_chunk` covers any tail that could still grow into a
        placeholder — i.e. an unclosed `[[…` or a lone trailing `[` that
        might become `[[` with the next chunk.
        """
        last_open = buffer.rfind("[[")
        if last_open != -1 and "]]" not in buffer[last_open:]:
            return buffer[:last_open], buffer[last_open:]
        if buffer.endswith("["):
            return buffer[:-1], "["
        return buffer, ""
