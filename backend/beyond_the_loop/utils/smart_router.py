import logging
import os
import time

from beyond_the_loop.config import ARENA_RANKINGS, LITELLM_MODEL_CONFIG
from beyond_the_loop.models.models import ModelMeta, ModelModel, ModelParams, Models
from beyond_the_loop.prompts import SMART_ROUTER_PROMPT
from beyond_the_loop.utils.structured_completion import (
    SmartRouterDecision,
    structured_completion,
)

log = logging.getLogger(__name__)


SMART_ROUTER_MODEL = ModelModel(
    id="Smart Router",
    name="Smart Router",
    meta=ModelMeta(),
    params=ModelParams(),
    is_active=True,
    updated_at=int(time.time()),
    created_at=int(time.time()),
    user_id=None,
    company_id="",
    base_model_id=None,
    access_control=None,
)

# Maps arena_rankings.json keys → litellm-config.yaml model names
_ARENA_TO_LITELLM: dict[str, str] = {
    "claude-haiku-4-5-20251001": "Claude 4.5 Haiku",
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "deepseek-r1": "DeepSeek R1",
    "deepseek-r1-0528": "DeepSeek R1-0528",
    "deepseek-v3.2": "DeepSeek-V3.2",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-3-flash": "Gemini 3 Flash",
    "gemini-3-pro": "Gemini 3 Pro",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash-Lite",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gpt-5-high": "GPT-5",
    "gpt-5-mini-high": "GPT-5 mini",
    "gpt-5.4": "GPT-5.4",
    "gpt-5.5": "GPT-5.5",
    "o3-2025-04-16": "GPT o3",
    "o4-mini-2025-04-16": "GPT o4-mini",
}

# Inverted: litellm model name → arena rankings dict (or empty if not in rankings)
_LITELLM_TO_ARENA: dict[str, dict] = {
    litellm_name: ARENA_RANKINGS[arena_key]
    for arena_key, litellm_name in _ARENA_TO_LITELLM.items()
    if arena_key in ARENA_RANKINGS
}


def _build_context_section(messages: list[dict] | None) -> str:
    if not messages:
        return ""
    prior = [m for m in messages if m.get("role") in ("user", "assistant")][:-1][-3:]
    if not prior:
        return ""
    lines = []
    for m in prior:
        content = m.get("content", "")
        if isinstance(content, list):
            content = next(
                (p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"),
                "",
            )
        label = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{label}: {str(content)[:400]}")
    return "### Recent Conversation:\n" + "\n".join(lines) + "\n\n"


async def _classify(user_message: str, user, messages, pii_active: bool) -> SmartRouterDecision:
    agent_model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

    from beyond_the_loop.pii.session import pii_note_prefix
    prompt = (
        pii_note_prefix(pii_active)
        + SMART_ROUTER_PROMPT
        .replace("{{CONVERSATION_CONTEXT}}", _build_context_section(messages))
        .replace("{{USER_MESSAGE}}", user_message)
    )

    return await structured_completion(
        messages=[{"role": "user", "content": prompt}],
        response_model=SmartRouterDecision,
        model=agent_model,
        user=user,
    )


def _arena_score(model_name: str, decision: SmartRouterDecision) -> int:
    rankings = _LITELLM_TO_ARENA.get(model_name, {})
    score = 0
    if decision.domain and decision.domain in rankings:
        score += rankings[decision.domain]
    if decision.task_type and decision.task_type in rankings:
        score += rankings[decision.task_type]
    elif decision.domain is None:
        score += rankings.get("overall", 500)
    # No arena data → use a neutral high value so ranked models win
    if score == 0:
        return 9999
    return score


async def select_model(
    user_message: str,
    user,
    messages: list[dict] | None = None,
    has_image_input: bool = False,
    pii_active: bool = False,
) -> tuple[ModelModel | None, SmartRouterDecision | None]:
    """
    Classify the user message via structured completion, then pick the best model:
    1. Hard-filter by required_tools and image_input capability.
    2. If image_generation required → only image-capable models survive (handled in step 1).
    3. Hard-filter by complexity → costFactor limit (complexity = max allowed costFactor, 1-4).
    4. Rank survivors by arena ranking score (domain + task_type, lower = better).
    Returns (None, None) if no suitable model can be found.
    """
    try:
        decision = await _classify(user_message, user, messages, pii_active)

        # image_generation is exclusive: our only image model doesn't support
        # any other tools, so drop the rest to avoid an unsolvable capability
        # filter. Also stops middleware from setting unrelated feature flags.
        if "image_generation" in decision.required_tools:
            decision.required_tools = ["image_generation"]

        # Lazy import to avoid circular dependency (main.py imports middleware.py)
        from open_webui.main import get_active_models
        active_models_result = await get_active_models(user=user)

        routable_models = [
            m for m in active_models_result["data"]
            if m.base_model_id is None
               and m.name != SMART_ROUTER_MODEL.name
               and m.is_active
               and not getattr(m, "fair_usage_limit_reached", False)
        ]

        # --- Step 1: capability hard-filter ---
        candidates = []
        for m in routable_models:
            cfg = LITELLM_MODEL_CONFIG.get(m.name, {})
            if ("web_search" in decision.required_tools) and not cfg.get("supports_web_search", False):
                continue
            if (
                "code_execution" in decision.required_tools
                or "document_creation" in decision.required_tools
            ) and not cfg.get("supports_code_execution", False):
                continue
            if "image_generation" in decision.required_tools and not cfg.get("supports_image_generation", False):
                continue
            if has_image_input and not cfg.get("supports_image_input", False):
                continue
            candidates.append(m)

        if not candidates:
            return None, decision

        # --- Step 3: complexity → costFactor filter ---
        def cost_of(m):
            return LITELLM_MODEL_CONFIG.get(m.name, {}).get("costFactor", decision.complexity)

        cost_filtered = [m for m in candidates if cost_of(m) <= decision.complexity]
        if not cost_filtered:
            # No model fits the requested cap (e.g. complexity=1 + code_execution
            # has no costFactor≤1 candidates) → relax to the cheapest available
            # costFactor instead of letting an expensive model through.
            min_cost = min(cost_of(m) for m in candidates)
            cost_filtered = [m for m in candidates if cost_of(m) <= min_cost]
        candidates = cost_filtered

        # --- Step 4: arena ranking (domain + task_type, lower score = better) ---
        best_model = min(candidates, key=lambda m: _arena_score(m.name, decision))
        return best_model, decision

    except Exception as e:
        log.exception(f"Smart Router model selection failed: {e}")
        return None, None
