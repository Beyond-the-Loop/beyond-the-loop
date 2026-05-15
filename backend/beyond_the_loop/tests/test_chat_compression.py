"""
Unit tests for beyond_the_loop/utils/chat_compression.py.

All external dependencies (DB, LiteLLM, _generate_summary) are mocked so the
tests run without a running server, database or the full pip environment.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_chat_compression.py -v
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub every heavy dependency BEFORE the module under test is imported.
# This avoids ModuleNotFoundError for litellm, sqlalchemy, etc.
# ---------------------------------------------------------------------------

def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# litellm stub
_litellm = _stub_module("litellm", model_cost={}, token_counter=MagicMock(return_value=10))

# beyond_the_loop.config stub
_stub_module("beyond_the_loop.config", LITELLM_MODEL_MAP={}, LITELLM_MODEL_CONFIG={})

# beyond_the_loop.models stubs
_stub_module("beyond_the_loop.models.chats", Chats=MagicMock())
_stub_module("beyond_the_loop.models.models", ModelModel=MagicMock, Models=MagicMock())

# beyond_the_loop.utils.structured_completion stub
_ChatSummaryResponse = MagicMock()
_structured_completion = AsyncMock()
_stub_module(
    "beyond_the_loop.utils.structured_completion",
    ChatSummaryResponse=_ChatSummaryResponse,
    structured_completion=_structured_completion,
)

# open_webui.env stub
_stub_module("open_webui.env", SRC_LOG_LEVELS={})

# Now it is safe to import the module under test
import beyond_the_loop.utils.chat_compression as cc  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(name: str = "GPT-4o") -> MagicMock:
    m = MagicMock()
    m.name = name
    return m


def _make_chat_data(compression: dict | None = None) -> MagicMock:
    chat_dict = {"title": "Test Chat"}
    if compression is not None:
        chat_dict["compression"] = compression
    cd = MagicMock()
    cd.chat = chat_dict
    return cd


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


# Patch targets (all resolved inside the already-imported module)
PATCH_GET_CHAT = "beyond_the_loop.utils.chat_compression.Chats.get_chat_by_id"
PATCH_SAVE = "beyond_the_loop.utils.chat_compression._save_compression_state"
PATCH_CTX_WINDOW = "beyond_the_loop.utils.chat_compression._get_context_window"
PATCH_COUNT_TOKENS = "beyond_the_loop.utils.chat_compression._count_tokens"
PATCH_GENERATE_SUMMARY = "beyond_the_loop.utils.chat_compression._generate_summary"


@pytest.fixture
def model():
    return _make_model("GPT-4o")


# ---------------------------------------------------------------------------
# Pure-function tests (no I/O, no mocks needed)
# ---------------------------------------------------------------------------


class TestContentAsText:
    def test_string_content(self):
        assert cc._content_as_text("hello world") == "hello world"

    def test_list_content(self):
        content = [{"type": "text", "text": "foo"}, {"type": "image_url", "url": "..."}]
        assert cc._content_as_text(content) == "foo"

    def test_list_multiple_text_parts(self):
        content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
        assert cc._content_as_text(content) == "hello world"

    def test_empty_list(self):
        assert cc._content_as_text([]) == ""

    def test_unknown_type_returns_empty(self):
        assert cc._content_as_text(42) == ""


class TestBuildSummaryBlock:
    def test_contains_summary_text(self):
        block = cc._build_summary_block("This is a summary.")
        assert "This is a summary." in block
        assert "CONVERSATION HISTORY SUMMARY" in block


class TestBuildPayload:
    def test_no_system_messages_creates_new_system_msg(self):
        conv = [_msg("user", "hi"), _msg("assistant", "hello")]
        result = cc._build_payload([], "My summary", conv)
        assert result[0]["role"] == "system"
        assert "My summary" in result[0]["content"]
        assert result[1:] == conv

    def test_with_system_message_merges_into_first(self):
        sys_msgs = [_msg("system", "You are helpful.")]
        conv = [_msg("user", "hi")]
        result = cc._build_payload(sys_msgs, "My summary", conv)
        assert result[0]["role"] == "system"
        assert "You are helpful." in result[0]["content"]
        assert "My summary" in result[0]["content"]
        assert result[-1] == conv[0]

    def test_multiple_system_messages_second_is_kept_intact(self):
        sys_msgs = [_msg("system", "First."), _msg("system", "Second.")]
        conv = [_msg("user", "hi")]
        result = cc._build_payload(sys_msgs, "Summary", conv)
        assert "First." in result[0]["content"]
        assert "Summary" in result[0]["content"]
        assert result[1] == sys_msgs[1]
        assert result[2] == conv[0]

    def test_original_system_msg_dict_not_mutated(self):
        original_content = "You are helpful."
        sys_msgs = [_msg("system", original_content)]
        cc._build_payload(sys_msgs, "Summary", [])
        assert sys_msgs[0]["content"] == original_content


# ---------------------------------------------------------------------------
# maybe_compress_chat — async tests via anyio
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestMaybeCompressChat:

    # ------------------------------------------------------------------
    # Guard-clause paths
    # ------------------------------------------------------------------

    async def test_empty_messages_returns_unchanged(self, model):
        form_data = {"messages": []}
        result = await cc.maybe_compress_chat(form_data, model, "chat-1")
        assert result is form_data

    async def test_last_message_not_user_returns_unchanged(self, model):
        form_data = {"messages": [_msg("assistant", "hello")]}
        result = await cc.maybe_compress_chat(form_data, model, "chat-1")
        assert result is form_data

    async def test_chat_not_found_returns_unchanged(self, model):
        form_data = {"messages": [_msg("user", "hi")]}
        with patch(PATCH_GET_CHAT, return_value=None):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")
        assert result is form_data

    # ------------------------------------------------------------------
    # First call — no compression state in DB
    # ------------------------------------------------------------------

    async def test_first_call_initialises_compression_and_saves(self, model):
        form_data = {"messages": [_msg("user", "Hello!")]}
        chat_data = _make_chat_data(compression=None)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=5),
            patch(PATCH_SAVE) as mock_save,
        ):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")

        # No summary yet → messages unchanged
        assert result["messages"] == [_msg("user", "Hello!")]
        saved = mock_save.call_args[0][1]
        assert saved["summary"] is None
        assert saved["messages"] == [_msg("user", "Hello!")]

    async def test_first_call_over_threshold_triggers_compression(self, model):
        user_msg = _msg("user", "A" * 5000)
        form_data = {"messages": [user_msg]}
        chat_data = _make_chat_data(compression=None)

        # 1st _count_tokens call: initial buffer check → 900 (over threshold 800)
        # 2nd call: after eviction → 0 (empty buffer)
        token_sequence = iter([900, 0])

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=1_000),
            patch(PATCH_COUNT_TOKENS, side_effect=token_sequence),
            patch(PATCH_GENERATE_SUMMARY, new=AsyncMock(return_value="Summary of first msg")),
            patch(PATCH_SAVE) as mock_save,
        ):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")

        saved = mock_save.call_args[0][1]
        assert saved["summary"] == "Summary of first msg"
        # The only message was evicted → buffer empty
        assert saved["messages"] == []
        # Summary must appear in the rebuilt payload
        assert any("Summary of first msg" in m.get("content", "") for m in result["messages"])

    # ------------------------------------------------------------------
    # Subsequent calls — compression state already exists
    # ------------------------------------------------------------------

    async def test_subsequent_call_appends_assistant_then_user(self, model):
        existing = {"messages": [_msg("user", "Turn 1")], "summary": None}
        form_data = {
            "messages": [
                _msg("user", "Turn 1"),
                _msg("assistant", "Answer 1"),
                _msg("user", "Turn 2"),
            ]
        }
        chat_data = _make_chat_data(compression=existing)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=10),
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        saved = mock_save.call_args[0][1]
        assert [m["role"] for m in saved["messages"]] == ["user", "assistant", "user"]

    async def test_subsequent_call_no_preceding_assistant_skips_append(self, model):
        existing = {"messages": [_msg("user", "Turn 1")], "summary": None}
        form_data = {
            "messages": [
                _msg("user", "Turn 1"),
                _msg("user", "Turn 2"),   # two user messages in a row
            ]
        }
        chat_data = _make_chat_data(compression=existing)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=10),
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        saved = mock_save.call_args[0][1]
        assert [m["role"] for m in saved["messages"]] == ["user", "user"]

    # ------------------------------------------------------------------
    # Eviction / compression logic
    # ------------------------------------------------------------------

    async def test_evicts_oldest_messages_until_under_threshold(self, model):
        # The buffer always ends with a user message (real invariant):
        # after turn 1 it contains [u1]; we now simulate turn 2 where
        # form_data brings in [u1, a1, u2] and we append a1 + u2.
        existing = {
            "messages": [_msg("user", "u1")],
            "summary": None,
        }
        form_data = {
            "messages": [
                _msg("user", "u1"),
                _msg("assistant", "a1"),
                _msg("user", "u2"),
            ]
        }
        chat_data = _make_chat_data(compression=existing)

        # After appending a1 + u2 the buffer is [u1, a1, u2] (3 messages).
        # Initial token check: 900 (over threshold 800)
        # After evicting u1:   [a1, u2] → 700 (under threshold) → stop
        token_sequence = iter([900, 700])

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=1_000),
            patch(PATCH_COUNT_TOKENS, side_effect=token_sequence),
            patch(PATCH_GENERATE_SUMMARY, new=AsyncMock(return_value="Summary")) as mock_gen,
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        # Only u1 was evicted
        evicted = mock_gen.call_args[1]["messages_to_summarize"]
        assert len(evicted) == 1
        assert evicted[0]["content"] == "u1"

        # Remaining buffer: a1 + u2
        saved = mock_save.call_args[0][1]
        assert [m["content"] for m in saved["messages"]] == ["a1", "u2"]

    async def test_evicts_multiple_messages_when_needed(self, model):
        existing = {
            "messages": [_msg("user", "u1"), _msg("assistant", "a1"), _msg("user", "u2")],
            "summary": None,
        }
        form_data = {
            "messages": [
                *existing["messages"],
                _msg("assistant", "a2"),
                _msg("user", "u3"),
            ]
        }
        chat_data = _make_chat_data(compression=existing)

        # Still over threshold after first two evictions, under after third
        token_sequence = iter([950, 900, 850, 400])

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=1_000),
            patch(PATCH_COUNT_TOKENS, side_effect=token_sequence),
            patch(PATCH_GENERATE_SUMMARY, new=AsyncMock(return_value="Big summary")) as mock_gen,
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        evicted = mock_gen.call_args[1]["messages_to_summarize"]
        assert len(evicted) == 3   # u1, a1, u2 evicted; a2, u3 remain

    async def test_rolling_summary_passed_to_generate(self, model):
        existing = {
            "messages": [_msg("user", "old msg")],
            "summary": "Previous summary text",
        }
        form_data = {"messages": [_msg("user", "old msg"), _msg("user", "new msg")]}
        chat_data = _make_chat_data(compression=existing)

        token_sequence = iter([900, 0])

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=1_000),
            patch(PATCH_COUNT_TOKENS, side_effect=token_sequence),
            patch(PATCH_GENERATE_SUMMARY, new=AsyncMock(return_value="Updated summary")) as mock_gen,
            patch(PATCH_SAVE),
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        assert mock_gen.call_args[1]["existing_summary"] == "Previous summary text"

    # ------------------------------------------------------------------
    # Payload rebuild
    # ------------------------------------------------------------------

    async def test_summary_merged_into_existing_system_message(self, model):
        existing = {"messages": [_msg("user", "old")], "summary": "Existing summary"}
        form_data = {
            "messages": [
                _msg("system", "Be helpful."),
                _msg("user", "old"),
                _msg("user", "new"),
            ]
        }
        chat_data = _make_chat_data(compression=existing)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=5),
            patch(PATCH_SAVE),
        ):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")

        first = result["messages"][0]
        assert first["role"] == "system"
        assert "Be helpful." in first["content"]
        assert "Existing summary" in first["content"]

    async def test_summary_creates_new_system_message_when_none_exists(self, model):
        existing = {"messages": [_msg("user", "old")], "summary": "Standalone summary"}
        form_data = {"messages": [_msg("user", "old"), _msg("user", "new")]}
        chat_data = _make_chat_data(compression=existing)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=5),
            patch(PATCH_SAVE),
        ):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")

        first = result["messages"][0]
        assert first["role"] == "system"
        assert "Standalone summary" in first["content"]

    async def test_no_summary_leaves_messages_unchanged(self, model):
        original = [_msg("user", "Turn 1"), _msg("user", "Turn 2")]
        form_data = {"messages": list(original)}
        chat_data = _make_chat_data(compression=None)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=5),
            patch(PATCH_SAVE),
        ):
            result = await cc.maybe_compress_chat(form_data, model, "chat-1")

        assert result["messages"] == original

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    async def test_save_always_called_when_chat_found(self, model):
        form_data = {"messages": [_msg("user", "hi")]}
        chat_data = _make_chat_data(compression=None)

        with (
            patch(PATCH_GET_CHAT, return_value=chat_data),
            patch(PATCH_CTX_WINDOW, return_value=10_000),
            patch(PATCH_COUNT_TOKENS, return_value=1),
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        mock_save.assert_called_once()
        call_chat_id, call_compression = mock_save.call_args[0]
        assert call_chat_id == "chat-1"
        assert call_compression["messages"] == [_msg("user", "hi")]
        assert call_compression["summary"] is None

    async def test_save_not_called_when_chat_not_found(self, model):
        form_data = {"messages": [_msg("user", "hi")]}
        with (
            patch(PATCH_GET_CHAT, return_value=None),
            patch(PATCH_SAVE) as mock_save,
        ):
            await cc.maybe_compress_chat(form_data, model, "chat-1")

        mock_save.assert_not_called()
