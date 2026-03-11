"""
Instructor-based structured completion utility.

Provides a thin async wrapper around the LiteLLM proxy that returns typed
Pydantic objects instead of raw LLM text, eliminating all manual JSON parsing.
"""

import logging
import os
from typing import Literal, Type, TypeVar

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

from beyond_the_loop.models.completions import Completions
from beyond_the_loop.models.models import ModelModel
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("MODELS", logging.INFO))

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Lazy-initialised global client (created on first use, module-level singleton)
# ---------------------------------------------------------------------------
_client: instructor.AsyncInstructor | None = None


def _get_client() -> instructor.AsyncInstructor:
    global _client
    if _client is None:
        base_url = os.getenv("OPENAI_API_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        _client = instructor.from_openai(
            AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
            )
        )
    return _client


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class ChatTitleResponse(BaseModel):
    title: str


class ImagePromptResponse(BaseModel):
    prompt: str


class SearchQuery(BaseModel):
    query: str
    result_limit: int


class SearchQueriesResponse(BaseModel):
    queries: list[SearchQuery]


class RagQueriesResponse(BaseModel):
    queries: list[str]


class ImageEditDecision(BaseModel):
    decision: Literal["yes", "no"]


class FileIntentDecision(BaseModel):
    intent: Literal["FULL", "RAG"]


class KnowledgeUseDecision(BaseModel):
    needs_knowledge: Literal["YES", "NO"]


class ToolSelectionDecision(BaseModel):
    tool: Literal["image_generation", "web_search", "code_interpreter", "none"]


# ---------------------------------------------------------------------------
# structured_completion helper
# ---------------------------------------------------------------------------

async def structured_completion(
    messages: list[dict],
    response_model: Type[T],
    model: ModelModel,
    user=None,
) -> T:
    """
    Call the LiteLLM proxy and return a typed Pydantic response.

    Args:
        messages: OpenAI-style message list.
        response_model: Pydantic model class for the expected response.
        model: LiteLLM model name or DB model ID/UUID.
        user: Optional user for credit tracking. If provided, subtracts credits
              and inserts a completion record.

    Returns:
        An instance of *response_model*.
    """
    client = _get_client()

    result, completion = await client.chat.completions.create_with_completion(
        model=model.name,
        messages=messages,
        response_model=response_model,
        temperature=0.0,
        max_retries=2,
    )

    if user is not None:
        try:
            subscription = payments_service.get_subscription(user.company_id)
            credit_cost = 0.0
            if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                credit_cost = await credit_service.subtract_credit_cost_by_user_and_response_and_model(
                    user, completion.model_dump()
                )
            Completions.insert_new_completion(user.id, model.name, credit_cost, None, True)
        except Exception:
            log.warning("Failed to track credits for structured completion", exc_info=True)

    return result
