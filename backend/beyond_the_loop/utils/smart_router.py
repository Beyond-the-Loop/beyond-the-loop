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
    rankings = ARENA_RANKINGS.get(model_name, {})
    score = 0
    if decision.domain and decision.domain in rankings:
        score += rankings[decision.domain]
    if decision.task_type and decision.task_type in rankings:
        score += rankings[decision.task_type]
    # No arena data → use a neutral high value so ranked models win
    if score == 0:
        return rankings.get("overall", 9999)
    return score


async def select_model(
    user_message: str,
    user,
    messages: list[dict] | None = None,
    has_image_input: bool = False,
    pii_active: bool = False,
) -> tuple[ModelModel | None, SmartRouterDecision | None, list[dict]]:
    """
    Classify the user message via structured completion, then pick the best model:
    1. Hard-filter by required_tools and image_input capability.
    2. If image_generation required → only image-capable models survive (handled in step 1).
    3. Hard-filter by complexity → costFactor limit (complexity = max allowed costFactor, 1-4).
    4. Rank survivors by arena ranking score (domain + task_type, lower = better).
    Returns (best_model, decision, ranked_candidates_info). On failure returns
    (None, None, []) or (None, decision, []) if classification succeeded but no
    model is selectable.
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

        ui_settings = getattr(getattr(user, "settings", None), "ui", None) or {}
        if ui_settings.get("smartRouterEuOnly"):
            routable_models = [
                m for m in routable_models
                if LITELLM_MODEL_CONFIG.get(m.name, {}).get("hosted_in") == "EU"
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
            if ("mcp" in decision.required_tools) and not cfg.get("supports_mcp", False):
                continue
            if "image_generation" in decision.required_tools and not cfg.get("supports_image_generation", False):
                continue
            if has_image_input and not cfg.get("supports_image_input", False):
                continue
            candidates.append(m)

        if not candidates:
            return None, decision, []

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
        scored = sorted(candidates, key=lambda m: _arena_score(m.name, decision))
        candidates_info = [{"name": m.name, "score": _arena_score(m.name, decision)} for m in scored]
        return scored[0], decision, candidates_info

    except Exception as e:
        log.exception(f"Smart Router model selection failed: {e}")
        return None, None
