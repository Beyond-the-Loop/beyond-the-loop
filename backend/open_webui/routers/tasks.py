import os

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel
import logging
import re

from beyond_the_loop.models.models import Models
from beyond_the_loop.routers.openai import generate_chat_completion
from open_webui.utils.task import (
    title_generation_template,
    query_generation_template,
    image_prompt_generation_template,
    tags_generation_template,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import TASKS

from beyond_the_loop.config import (
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
    WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE,
    RAG_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE
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
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


class TaskConfigForm(BaseModel):
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_TAGS_GENERATION: bool
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: str


@router.post("/config/update")
async def update_task_config(
    request: Request, form_data: TaskConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = (
        form_data.TITLE_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = (
        form_data.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
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

    request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
        form_data.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    )

    return {
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    task_model_id = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id).id

    log.debug(
        f"generating chat title using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE

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

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.TITLE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
            "agent_or_task_prompt": True
        },
    }

    try:
        return await generate_chat_completion(form_data=payload, user=user)
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/tags/completions")
async def generate_chat_tags(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_TAGS_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Tags generation is disabled"},
        )

    task_model_id = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id).id

    log.debug(
        f"generating chat tags using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE

    content = tags_generation_template(
        template, form_data["messages"], {"first_name": user.first_name, "last_name": user.last_name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.TAGS_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
            "agent_or_task_prompt": True
        },
    }

    try:
        return await generate_chat_completion(form_data=payload, user=user)
    except Exception as e:
        log.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/image_prompt/completions")
async def generate_image_prompt(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    task_model_id = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id).id

    log.debug(
        f"generating image prompt using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE

    content = image_prompt_generation_template(
        template,
        form_data["messages"],
        user={
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.IMAGE_PROMPT_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
            "agent_or_task_prompt": True
        },
    }

    try:
        return await generate_chat_completion(form_data=payload, user=user)
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


async def generate_queries(query_type: str, messages: list[dict], chat_id: str|None, user):
    task_model_id = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id).id

    log.debug(
        f"generating {query_type} queries using model {task_model_id} for user {user.email}"
    )

    response_format = None

    if query_type == "web_search":
        template = WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "search_queries",
                "schema": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query text"
                                    },
                                    "result_limit": {
                                        "type": "integer",
                                        "description": "Maximum number of results to retrieve"
                                    }
                                },
                                "required": ["query", "result_limit"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["queries"],
                    "additionalProperties": False
                }
            }
        }
    else:
        template = RAG_QUERY_GENERATION_PROMPT_TEMPLATE

    content = query_generation_template(template, messages)

    payload = {
        "model": task_model_id,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "stream": False,
        "response_format": response_format,
        "metadata": {
            "chat_id": chat_id,
            "task": str(TASKS.QUERY_GENERATION),
            "agent_or_task_prompt": True
        }
    }

    try:
        return await generate_chat_completion(form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )