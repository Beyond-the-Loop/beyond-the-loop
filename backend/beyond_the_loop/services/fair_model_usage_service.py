from fastapi import HTTPException

from beyond_the_loop.models.completions import Completions
from beyond_the_loop.config import LITELLM_MODEL_CONFIG


class FairModelUsageService:
    def __init__(self):
        pass

    def get_fair_usage_limit_reached_models(self, user, model_names: list[str], plan: str) -> set[str]:
        """Returns a set of model names that have reached their fair usage limit.
        Uses a single DB query for all models instead of one per model.
        """
        if not model_names:
            return set()

        if plan == "free":
            limit_key = "allowed_messages_per_three_hours_free"
        elif plan == "premium":
            limit_key = "allowed_messages_per_three_hours_premium"
        else:
            return set()

        model_limits = {
            name: LITELLM_MODEL_CONFIG.get(name, {}).get(limit_key)
            for name in model_names
        }
        models_with_limit = [name for name, limit in model_limits.items() if limit]

        if not models_with_limit:
            return set()

        counts = Completions.get_completions_count_last_three_hours_by_user_and_models(user.id, models_with_limit)

        return {
            name for name in models_with_limit
            if counts.get(name, 0) >= model_limits[name]
        }

    def check_for_fair_model_usage(self, user, model_name: str, plan: str):
        model_config = LITELLM_MODEL_CONFIG.get(model_name, {})

        if plan == "free":
            allowed_messages_per_three_hours = model_config.get("allowed_messages_per_three_hours_free")
        elif plan == "premium":
            allowed_messages_per_three_hours = model_config.get("allowed_messages_per_three_hours_premium")
        else:
            raise HTTPException(status_code=400, detail="Invalid plan.")

        # If no value -> no access to model
        if not allowed_messages_per_three_hours:
            raise HTTPException(status_code=400, detail="No access to model.")

        messages_last_three_hours = Completions.get_completions_last_three_hours_by_user_and_model(user.id, model_name)

        if messages_last_three_hours >= allowed_messages_per_three_hours:
            raise HTTPException(
                status_code=429,
                detail=f"You have reached the maximum number ({allowed_messages_per_three_hours}) of messages per three hours. Please try again later or use a different model.",
            )

fair_model_usage_service = FairModelUsageService()
