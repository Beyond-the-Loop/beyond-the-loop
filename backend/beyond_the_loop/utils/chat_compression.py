from __future__ import annotations

import logging
import litellm

from beyond_the_loop.config import LITELLM_MODEL_CONFIG, LITELLM_MODEL_MAP
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.folders import Folders
from beyond_the_loop.models.models import ModelModel
from beyond_the_loop.prompts import CHAT_COMPRESSION_NOTICE
from beyond_the_loop.utils.structured_completion import ChatSummaryResponse, structured_completion
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_COMPRESSION_THRESHOLD = 0.8
MIN_COMPRESSION_THRESHOLD = 0.6
MAX_COMPRESSION_THRESHOLD = 0.8
DEFAULT_CONTEXT_WINDOW = 128_000

# ---------------------------------------------------------------------------
# Token counting & context window helpers
# ---------------------------------------------------------------------------


def _get_compression_threshold(model_display_name: str) -> float:
    """
    Scale the compression threshold by the model's costFactor so expensive
    models compress earlier than cheap ones. Range: 60% (most expensive)
    to 80% (cheapest).
    """
    cost_factor = LITELLM_MODEL_CONFIG.get(model_display_name, {}).get("costFactor")
    if cost_factor is None:
        return DEFAULT_COMPRESSION_THRESHOLD

    return max(
        MIN_COMPRESSION_THRESHOLD,
        min(MAX_COMPRESSION_THRESHOLD, 0.85 - cost_factor * 0.05),
    )


def _get_context_window(model_display_name: str) -> int:
    litellm_name = LITELLM_MODEL_MAP.get(model_display_name)
    if litellm_name:
        try:
            info = litellm.model_cost.get(litellm_name, {})
            window = info.get("max_input_tokens") or info.get("max_tokens")
            if window:
                return int(window)
        except Exception:
            pass
    return DEFAULT_CONTEXT_WINDOW


def _count_tokens(messages: list[dict], model_display_name: str) -> int:
    litellm_name = LITELLM_MODEL_MAP.get(model_display_name)
    try:
        return litellm.token_counter(
            model=litellm_name or model_display_name,
            messages=messages,
        )
    except Exception:
        log.warning("Could not count tokens for model %s", model_display_name, exc_info=True)

        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += len(part.get("text", "")) // 4
            total += 4
        return total


def _drop_to_budget(
    messages: list[dict],
    model_display_name: str,
    budget_tokens: int,
    min_keep: int = 0,
) -> list[dict]:
    """Pop oldest messages until the remainder fits `budget_tokens` (keeping at least
    `min_keep`). Mutates `messages` in place and returns the dropped messages (oldest
    first)."""
    dropped: list[dict] = []
    while len(messages) > min_keep and _count_tokens(messages, model_display_name) > budget_tokens:
        dropped.append(messages.pop(0))
    return dropped


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def _content_as_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _save_compression_state(chat_id: str, compression: dict) -> None:
    chat_data = Chats.get_chat_by_id(chat_id)
    if not chat_data:
        return

    chat = chat_data.chat
    chat["compression"] = compression
    Chats.update_chat_by_id(chat_id, chat)


# ---------------------------------------------------------------------------
# Summarisation
# ---------------------------------------------------------------------------


async def _generate_summary(
    existing_summary: str | None,
    messages_to_summarize: list[dict],
    agent_model: ModelModel,
    pii_active: bool = False,
    user=None,
) -> str:
    from beyond_the_loop.prompts import CHAT_SUMMARY_PROMPT
    from beyond_the_loop.pii.session import pii_note_prefix

    if existing_summary:
        user_content = (
            f"[PREVIOUS SUMMARY]\n{existing_summary}\n\n"
            "[NEW MESSAGES TO INTEGRATE INTO THE SUMMARY]\n"
        )
    else:
        user_content = "[MESSAGES TO SUMMARIZE]\n"

    for msg in messages_to_summarize:
        role = msg.get("role", "unknown").upper()
        text = _content_as_text(msg.get("content", ""))
        user_content += f"{role}: {text}\n\n"

    result = await structured_completion(
        messages=[
            {"role": "system", "content": pii_note_prefix(pii_active) + CHAT_SUMMARY_PROMPT},
            {"role": "user", "content": user_content.strip()},
        ],
        response_model=ChatSummaryResponse,
        model=agent_model,
        user=user,
    )

    return result.summary


# ---------------------------------------------------------------------------
# History extraction
# ---------------------------------------------------------------------------


def _extract_history_messages(chat: dict) -> list[dict]:
    """Linearise a stored chat into an ordered [{role, content}] list for summarising."""
    flat = chat.get("messages")
    if isinstance(flat, list) and flat:
        return [
            {"role": m.get("role"), "content": m.get("content", "")}
            for m in flat
            if isinstance(m, dict) and m.get("role")
        ]

    history = chat.get("history") or {}
    messages = history.get("messages") or {}
    node_id = history.get("currentId")

    ordered: list[dict] = []
    seen: set = set()
    while node_id and node_id in messages and node_id not in seen:
        seen.add(node_id)
        msg = messages[node_id]
        ordered.append({"role": msg.get("role"), "content": msg.get("content", "")})
        node_id = msg.get("parentId")

    ordered.reverse()
    return [m for m in ordered if m.get("role")]


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def _build_summary_block(summary_text: str) -> str:
    return (
        "[CONVERSATION HISTORY SUMMARY]\n"
        "The following is a condensed summary of the earlier conversation. "
        "Use it as context when answering the user.\n\n"
        f"{summary_text}"
    )


def _merge_system_block(messages: list[dict], addition: str) -> list[dict]:
    """Append `addition` to the first system message (or prepend a new one), keeping
    every other message in order."""
    system_msgs = [m for m in messages if m.get("role") == "system"]
    others = [m for m in messages if m.get("role") != "system"]
    if system_msgs:
        merged = {**system_msgs[0], "content": system_msgs[0]["content"] + "\n\n" + addition}
        return [merged, *system_msgs[1:], *others]
    return [{"role": "system", "content": addition}, *others]


def _build_payload(
    system_msgs: list[dict],
    summary_text: str | None,
    conversational_messages: list[dict],
    notice_text: str | None = None,
) -> list[dict]:
    blocks: list[str] = []
    if summary_text:
        blocks.append(_build_summary_block(summary_text))
    if notice_text:
        blocks.append(notice_text)

    combined = [*system_msgs, *conversational_messages]
    if not blocks:
        return combined

    return _merge_system_block(combined, "\n\n".join(blocks))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def maybe_compress_chat(
    form_data: dict,
    model: ModelModel,
    chat_id: str,
    event_emitter=None,
    pii_active: bool = False,
    user=None,
) -> dict:
    all_messages: list[dict] = form_data.get("messages", [])

    if not all_messages:
        return form_data

    latest_user_msg = all_messages[-1]

    if latest_user_msg.get("role") != "user":
        return form_data

    # Load existing compression state from DB
    chat_data = Chats.get_chat_by_id(chat_id)

    if not chat_data:
        log.warning("[chat_compression] chat %s not found in DB — skipping", chat_id)
        return form_data

    compression: dict | None = chat_data.chat.get("compression")

    if compression is not None:
        prev_msg = all_messages[-2] if len(all_messages) >= 2 else None

        if prev_msg and prev_msg.get("role") == "assistant":
            compression["messages"].append(prev_msg)

        compression["messages"].append(latest_user_msg)
    else:
        compression = {"messages": [latest_user_msg], "summary": None}

    # -----------------------------------------------------------------------
    # Check whether compression["messages"] exceeds the context window
    # -----------------------------------------------------------------------
    context_window = _get_context_window(model.name)
    threshold_pct = _get_compression_threshold(model.name)
    threshold_tokens = int(context_window * threshold_pct)
    current_tokens = _count_tokens(compression["messages"], model.name)
    show_continue_chat_hint = False
    did_compress = False

    if current_tokens > threshold_tokens:
        show_continue_chat_hint = True
        did_compress = True

        if event_emitter:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "chat_compression",
                        "description": "Compressing chat history",
                        "done": False,
                    },
                }
            )

        await compress_chat(
            compression,
            agent_model=model,
            keep_budget=threshold_tokens,
            pii_active=pii_active,
            user=user,
        )

    if show_continue_chat_hint:
        form_data["__continue_chat_action__"] = {
            "action": "continue_chat_button",
            "reason": "chat_too_long",
        }

    if did_compress and event_emitter:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "chat_compression",
                    "description": "Compressing chat history",
                    "done": True,
                },
            }
        )

    # -----------------------------------------------------------------------
    # Rebuild the LiteLLM payload when there is something to inject into the
    # system prompt (a summary and/or a "chat is long" notice).
    # -----------------------------------------------------------------------
    summary = compression.get("summary")
    if summary or show_continue_chat_hint:
        system_msgs = [m for m in all_messages if m.get("role") == "system"]
        form_data["messages"] = _build_payload(
            system_msgs,
            summary,
            compression["messages"],
            # Only nudge "start a new chat" when THIS chat is actually long — not merely
            # because a carried-over summary exists (continued chats begin with one).
            notice_text=CHAT_COMPRESSION_NOTICE if show_continue_chat_hint else None,
        )

    # Persist the updated compression state
    _save_compression_state(chat_id, compression)

    return form_data


async def compress_chat(
    compression: dict,
    agent_model: ModelModel,
    keep_budget: int,
    pii_active: bool = False,
    user=None,
) -> dict:
    """Recursive compression shared by maybe_compress_chat and build_continuation_seed:
    drop the oldest messages beyond `keep_budget` tokens and fold them into
    compression["summary"] (keep_budget=0 folds the whole history). Mutates and returns
    compression."""
    dropped = _drop_to_budget(
        compression["messages"], agent_model.name, keep_budget, min_keep=0
    )

    if not dropped:
        return compression

    compression["summary"] = await _generate_summary(
        existing_summary=compression.get("summary"),
        messages_to_summarize=dropped,
        agent_model=agent_model,
        pii_active=pii_active,
        user=user,
    )

    return compression


async def build_continuation_seed(
    chat: dict,
    agent_model: ModelModel,
    chat_id: str | None = None,
    pii_active: bool = False,
    user=None,
) -> dict | None:
    """Build the "Continue in new chat" seed: summarise the whole history fresh (never
    reuse the stored summary — it may be stale/inherited) via the shared compress_chat
    with keep_budget=0, so nothing is dropped."""
    messages = _extract_history_messages(chat)

    if not messages:
        return None

    if pii_active and chat_id:
        from beyond_the_loop.pii.session import PIISession, anonymize_messages

        pii_session = PIISession(chat_id)
        anonymize_messages(messages, pii_session)
        pii_session.save()

    compression = {"messages": messages, "summary": None}
    await compress_chat(
        compression, agent_model=agent_model, keep_budget=0, pii_active=pii_active, user=user
    )

    summary = compression.get("summary")
    if not summary or not summary.strip():
        return None

    return {"messages": [], "summary": summary}


# ---------------------------------------------------------------------------
# Project context (folder = project) — Projects v2
# ---------------------------------------------------------------------------


async def gather_and_inject_folder_context(
    form_data: dict,
    chat_id: str,
    model: ModelModel,
    event_emitter=None,
    pii_active: bool = False,
    user=None,
) -> dict:
    """If this chat belongs to a folder (project): for every OTHER chat in the project,
    make sure its own compression.summary is current — if it has pending compression
    ["messages"], fold them in first via compress_chat — then collect the summaries into
    folder.meta['summaries'] and append them to the prompt. Each chat keeps only its own
    summary."""
    if not user or not chat_id:
        return form_data

    chat_data = Chats.get_chat_by_id(chat_id)
    if not chat_data or not chat_data.folder_id:
        return form_data

    folder = Folders.get_folder_by_id_and_user_id(chat_data.folder_id, user.id)
    if not folder:
        return form_data

    siblings = [
        c
        for c in Chats.get_chats_by_folder_id_and_user_id(chat_data.folder_id, user.id)
        if c.id != chat_id
    ]
    if not siblings:
        return form_data

    summaries: dict = {}
    emitted = False

    for sib in siblings:
        compression = sib.chat.get("compression") or {}
        summary = compression.get("summary")

        # Only summary, no pending messages → already up to date. Pending messages →
        # fold them into the summary first (compress_chat), then persist the chat's state.
        if compression.get("messages"):
            if event_emitter and not emitted:
                await event_emitter(
                    {"type": "status", "data": {"action": "project_context",
                     "description": "Aktualisiere Projektkontext", "done": False}}
                )
                emitted = True
            await compress_chat(compression, agent_model=model, keep_budget=0,
                                pii_active=pii_active, user=user)
            _save_compression_state(sib.id, compression)
            summary = compression.get("summary")

        if summary:
            summaries[sib.id] = {"title": sib.title, "summary": summary}

    # The folder holds the list of all its chats' summaries (write only on change).
    if summaries != (folder.meta or {}).get("summaries"):
        Folders.update_folder_meta_by_id_and_user_id(
            chat_data.folder_id, user.id, {**(folder.meta or {}), "summaries": summaries}
        )

    blocks = [f"[{e['title']}]\n{e['summary']}" for e in summaries.values() if e.get("summary")]
    if not blocks:
        return form_data

    context = (
        "[PROJECT CONTEXT]\n"
        "Current summaries of the OTHER chats in this project, refreshed for THIS message. "
        "This is the authoritative, up-to-date list — if it differs from anything said "
        "earlier in this conversation, trust this list over your previous answers.\n\n"
        + "\n\n".join(blocks)
    )
    form_data["messages"] = _merge_system_block(form_data.get("messages", []), context)
    return form_data
