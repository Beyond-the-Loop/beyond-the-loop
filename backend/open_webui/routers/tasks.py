import os

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel
import logging
import re

from beyond_the_loop.models.models import Models
from open_webui.utils.task import (
    title_generation_template,
    query_generation_template,
    tags_generation_template,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import TASKS

from beyond_the_loop.config import (
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE,
    RAG_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE
)
from beyond_the_loop.utils.structured_completion import (
    structured_completion,
    ChatTitleResponse,
    SearchQueriesResponse,
    RagQueriesResponse,
)
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


##################################
#
# Task Endpoints
#
##################################


@router.get("/config")
async def get_task_config(request: Request, user=Depends(get_verified_user)):
    return {
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
    }


class TaskConfigForm(BaseModel):
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_TAGS_GENERATION: bool


@router.post("/config/update")
async def update_task_config(
    request: Request, form_data: TaskConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = (
        form_data.TITLE_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = (
        form_data.ENABLE_AUTOCOMPLETE_GENERATION
    )
    request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
        form_data.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
    )

    request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = (
        form_data.TAGS_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.ENABLE_TAGS_GENERATION = form_data.ENABLE_TAGS_GENERATION

    return {
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
    }


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    task_model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

    log.debug(
        f"generating chat title using model {task_model.id} for user {user.email} "
    )

    if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE

    pii_active = bool(form_data.get("pii_active", False))
    messages = form_data["messages"]

    # Remove reasoning details from the messages
    for message in messages:
        message["content"] = re.sub(
            r"<details\s+type=\"reasoning\"[^>]*>.*?<\/details>",
            "",
            message["content"],
            flags=re.S,
        ).strip()

    content = title_generation_template(
        template,
        messages,
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "location": user.info.get("location") if user.info else None,
        },
    )

    from beyond_the_loop.pii.session import pii_note_prefix
    content = pii_note_prefix(pii_active) + content

    try:
        result = await structured_completion(
            messages=[{"role": "user", "content": content}],
            response_model=ChatTitleResponse,
            model=task_model,
            user=user,
        )
        return {"title": result.title}
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


async def generate_queries(
    query_type: str, messages: list[dict], chat_id: str | None, user,
    pii_active: bool = False,
):
    task_model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

    log.debug(
        f"generating {query_type} queries using model {task_model.id} for user {user.email}"
    )

    from beyond_the_loop.pii.session import pii_note_prefix
    note = pii_note_prefix(pii_active)

    if query_type == "web_search":
        template = WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE
        content = note + query_generation_template(template, messages)
        result = await structured_completion(
            messages=[{"role": "user", "content": content}],
            response_model=SearchQueriesResponse,
            model=task_model,
        )
        return {"queries": [q.model_dump() for q in result.queries]}
    else:
        template = RAG_QUERY_GENERATION_PROMPT_TEMPLATE
        content = note + query_generation_template(template, messages)
        result = await structured_completion(
            messages=[{"role": "user", "content": content}],
            response_model=RagQueriesResponse,
            model=task_model,
        )
        return {"queries": result.queries}