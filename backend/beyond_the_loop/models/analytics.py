from pydantic import BaseModel, field_validator
from typing import List, Optional

class TopModelItem(BaseModel):
    model: str
    credits_used: int
    message_count: int

class TopModelsResponse(BaseModel):
    items: List[TopModelItem]

    @classmethod
    def from_query_result(cls, top_models):
        return cls(
            items=[
                TopModelItem(
                    model=model,
                    credits_used=credits_used,
                    message_count=message_count,
                )
                for model, credits_used, message_count in top_models
            ]
        )

class TopUserItem(BaseModel):
    user_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    profile_image_url: Optional[str]

    total_credits_used: int
    message_count: int
    assistant_message_percentage: float

    top_model: Optional[str]
    top_assistant: Optional[str]

class TopUsersResponse(BaseModel):
    top_users: List[TopUserItem]

    @classmethod
    def from_query_result(cls, top_users):
        return cls(
            top_users=[
                TopUserItem(
                    user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    profile_image_url=profile_image_url,
                    total_credits_used=total_credits_used,
                    message_count=message_count,
                    assistant_message_percentage=float(
                        round(assistant_message_percentage or 0, 2)
                    ),
                    top_model=top_model,
                    top_assistant=top_assistant,
                )
                for (
                    user_id,
                    total_credits_used,
                    message_count,
                    assistant_message_percentage,
                    first_name,
                    last_name,
                    email,
                    profile_image_url,
                    top_model,
                    top_assistant,
                ) in top_users
            ]
        )

class TopAssistantItem(BaseModel):
    assistant: str
    total_credits_used: int
    message_count: int

class TopAssistantsResponse(BaseModel):
    top_assistants: List[TopAssistantItem]

    @classmethod
    def from_query_result(cls, top_assistants):
        return cls(
            top_assistants=[
                TopAssistantItem(
                    assistant=assistant,
                    total_credits_used=total_credits_used,
                    message_count=message_count,
                )
                for (
                    assistant,
                    total_credits_used,
                    message_count,
                ) in top_assistants
            ]
        )

class MonthlyMessageItem(BaseModel):
    period: str
    message_count: int


class MonthlyPercentageChangeItem(BaseModel):
    period: str
    percentage_change: float

    @field_validator("percentage_change", mode="before")
    @classmethod
    def round_percentage(cls, v):
        if v in (None, "N/A"):
            return 0.0
        return round(float(v), 2)


class YearlyMessageItem(BaseModel):
    period: str
    message_count: int


class YearlyPercentageChangeItem(BaseModel):
    period: str
    percentage_change: float

    @field_validator("percentage_change", mode="before")
    @classmethod
    def round_percentage(cls, v):
        if v in (None, "N/A"):
            return 0.0
        return round(float(v), 2)


class TotalMessagesResponse(BaseModel):
    monthly_messages: List[MonthlyMessageItem]
    monthly_percentage_changes: List[MonthlyPercentageChangeItem]
    yearly_messages: List[YearlyMessageItem]
    yearly_percentage_changes: List[YearlyPercentageChangeItem]

    @classmethod
    def from_data(
        cls,
        monthly_data: dict,
        monthly_percentage_changes: dict,
        yearly_data: dict,
        yearly_percentage_changes: dict,
    ):
        return cls(
            monthly_messages=[
                MonthlyMessageItem(
                    period=period,
                    message_count=value
                )
                for period, value in monthly_data.items()
            ],
            monthly_percentage_changes=[
                MonthlyPercentageChangeItem(
                    period=period,
                    percentage_change=value
                )
                for period, value in monthly_percentage_changes.items()
            ],
            yearly_messages=[
                YearlyMessageItem(
                    period=period,
                    message_count=value
                )
                for period, value in yearly_data.items()
            ],
            yearly_percentage_changes=[
                YearlyPercentageChangeItem(
                    period=period,
                    percentage_change=value
                )
                for period, value in yearly_percentage_changes.items()
            ],
        )

class PowerUserItem(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    profile_image_url: str | None = None
    total_credits_used: float
    message_count: int

class PowerUsersResponse(BaseModel):
    power_users: List[PowerUserItem]
    power_users_count: int
    total_users: int
    power_users_percentage: float

    @classmethod
    def from_data(cls, data: dict):
        """
        Create a PowerUsersResponse from a raw dictionary.
        Ensures that each item in 'power_users' is a PowerUserItem.
        """
        power_users_list = [PowerUserItem(**u) for u in data.get("power_users", [])]

        return cls(
            power_users=power_users_list,
            power_users_count=data.get("power_users_count", len(power_users_list)),
            total_users=data.get("total_users", 0),
            power_users_percentage=round(float(data.get("power_users_percentage", 0)), 2)
        )

class TotalUsersResponse(BaseModel):
    total_users: int

class TotalAssistantsResponse(BaseModel):
    total_assistants: int

class EngagementScoreResponse(BaseModel):
    total_users: int
    active_users: int
    adoption_rate: float

    @classmethod
    def from_data(cls, data: dict):
        """
        Create an EngagementScoreResponse from a raw dictionary.
        Automatically rounds adoption_rate to 2 decimals.
        """
        return cls(
            total_users=int(data.get("total_users", 0)),
            active_users=int(data.get("active_users", 0)),
            adoption_rate=round(float(data.get("adoption_rate", 0)), 2)
        )
