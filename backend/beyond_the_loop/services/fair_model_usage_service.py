from fastapi import HTTPException

from beyond_the_loop.models.completions import Completions
from beyond_the_loop.config import LITELLM_MODEL_CONFIG


class FairModelUsageService:
    def __init__(self):
        pass

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
