from fastapi import HTTPException

from beyond_the_loop.models.completions import Completions
from beyond_the_loop.models.model_costs import ModelCosts


class FairModelUsageService:
    def __init__(self):
        """Initialize the CreditService."""
        pass

    def check_for_fair_model_usage(self, user, model_name):
        allowed_messages_per_three_hours = ModelCosts.get_allowed_messages_per_three_hours_by_name(model_name)

        if not allowed_messages_per_three_hours:
            return

        messages_last_three_hours = Completions.get_completions_last_three_hours_by_user_and_model(user.id, model_name)

        if messages_last_three_hours >= allowed_messages_per_three_hours:
            raise HTTPException(
                status_code=429,
                detail=f"You have reached the maximum number ({allowed_messages_per_three_hours}) of messages per three hours. Please try again later or use a different model.",
            )

fair_model_usage_service = FairModelUsageService()