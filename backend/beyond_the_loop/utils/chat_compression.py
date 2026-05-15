import logging
import litellm

from beyond_the_loop.config import LITELLM_MODEL_CONFIG, LITELLM_MODEL_MAP
from beyond_the_loop.models.chats import Chats
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
    )

    return result.summary


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

    if not blocks:
        return [*system_msgs, *conversational_messages]

    addition = "\n\n".join(blocks)
    if system_msgs:
        merged = {**system_msgs[0], "content": system_msgs[0]["content"] + "\n\n" + addition}
        return [merged, *system_msgs[1:], *conversational_messages]
    return [{"role": "system", "content": addition}, *conversational_messages]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def maybe_compress_chat(
    form_data: dict,
    model: ModelModel,
    chat_id: str,
    event_emitter=None,
    pii_active: bool = False,
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

    if current_tokens > threshold_tokens:
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

        messages_to_compress: list[dict] = []

        while compression["messages"] and current_tokens > threshold_tokens:
            removed = compression["messages"].pop(0)
            messages_to_compress.append(removed)
            current_tokens = _count_tokens(compression["messages"], model.name)

        existing_summary = compression.get("summary")

        new_summary = await _generate_summary(
            existing_summary=existing_summary,
            messages_to_summarize=messages_to_compress,
            agent_model=model,
            pii_active=pii_active,
        )
        compression["summary"] = new_summary

        if event_emitter:
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
    if summary:
        system_msgs = [m for m in all_messages if m.get("role") == "system"]
        form_data["messages"] = _build_payload(
            system_msgs,
            summary,
            compression["messages"],
            notice_text=CHAT_COMPRESSION_NOTICE,
        )

    # Persist the updated compression state
    _save_compression_state(chat_id, compression)

    return form_data
