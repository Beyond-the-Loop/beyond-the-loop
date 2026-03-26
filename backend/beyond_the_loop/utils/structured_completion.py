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

from beyond_the_loop.models.models import ModelModel
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
) -> T:
    """
    Call the LiteLLM proxy and return a typed Pydantic response.

    Args:
        messages: OpenAI-style message list.
        response_model: Pydantic model class for the expected response.
        temperature: Sampling temperature (default 0.0 for deterministic outputs).
        model: LiteLLM model name or DB model ID/UUID. Defaults to
               DEFAULT_AGENT_MODEL.value (resolved via resolve_model_name).

    Returns:
        An instance of *response_model*.
    """
    client = _get_client()

    return await client.chat.completions.create(
        model=model.name,
        messages=messages,
        response_model=response_model,
        temperature=0.0,
        max_retries=2,
    )
