"""Public OpenAI-compatible API surfaced under /api/openai for sk-... key holders."""

import logging
import os

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from beyond_the_loop.models.files import Files
from beyond_the_loop.models.models import Models, filter_base_models_by_plan
from beyond_the_loop.routers.files import upload_file
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service

from open_webui.env import AIOHTTP_CLIENT_TIMEOUT
from open_webui.utils.auth import get_current_api_key_user

log = logging.getLogger(__name__)

router = APIRouter()


def _openai_error(status_code: int, message: str, err_type: str = "upstream_error") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": err_type, "code": status_code}},
    )


async def _proxy_to_litellm(path: str, payload: dict) -> dict | JSONResponse:
    async with aiohttp.ClientSession(
        trust_env=True,
        timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
    ) as session:
        async with session.post(
            f"{os.getenv('OPENAI_API_BASE_URL')}{path}",
            json=payload,
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
            },
        ) as upstream:
            if upstream.status >= 400:
                body_text = await upstream.text()
                log.warning(
                    "LiteLLM upstream error on %s: status=%s body=%s payload_model=%s",
                    path, upstream.status, body_text, payload.get("model"),
                )
                return _openai_error(upstream.status, body_text or upstream.reason)
            try:
                return await upstream.json()
            except Exception as exc:
                log.exception("Failed to parse LiteLLM response on %s", path)
                return _openai_error(500, f"Invalid upstream response: {exc}")


def _append_file_to_chat_messages(messages: list, file_content: str) -> None:
    if not file_content or not messages:
        return
    last_user_message = next(
        (m for m in reversed(messages) if m.get("role") == "user"), None
    )
    if last_user_message is None:
        return
    last_user_message["content"] = last_user_message.get("content", "") + file_content


def _append_file_to_responses_input(input_items: list, file_content: str) -> None:
    if not file_content or not input_items:
        return
    last_user_message = next(
        (m for m in reversed(input_items) if m.get("role") == "user"), None
    )
    if last_user_message is None:
        return
    content = last_user_message.get("content")
    if isinstance(content, list):
        content.append({"type": "input_text", "text": file_content})
    else:
        last_user_message["content"] = [{"type": "input_text", "text": file_content}]


def _resolve_file_or_404(file_id: str):
    file = Files.get_file_by_id(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


def _responses_usage_as_chat_completion(response: dict) -> dict:
    # Why: credit_service uses litellm.completion_cost which reads usage.prompt_tokens /
    # completion_tokens — the Responses API uses input_tokens / output_tokens.
    usage = response.get("usage", {}) or {}
    return {
        "model": response.get("model"),
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get(
                "total_tokens",
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
        },
    }


@router.get("/models")
async def list_models(user=Depends(get_current_api_key_user)):
    subscription = payments_service.get_subscription(user.company_id)
    plan = subscription.get("plan")
    base_models = Models.get_active_base_models_by_comany_and_user(
        user.company_id, user.id, user.role
    )
    base_models = filter_base_models_by_plan(base_models, plan, user.company_id)
    return {
        "object": "list",
        "data": [
            {
                "id": m.name,
                "object": "model",
                "created": int(m.created_at) if getattr(m, "created_at", None) else 0,
                "owned_by": "beyond-the-loop",
            }
            for m in base_models
        ],
    }


@router.post("/chat/completions")
async def chat_completions(request: dict, user=Depends(get_current_api_key_user)):
    await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)
    request["stream"] = False

    file_id = request.get("metadata", {}).get("file_id")
    if file_id:
        file = _resolve_file_or_404(file_id)
        _append_file_to_chat_messages(
            request.get("messages", []), file.data.get("content", "")
        )

    response = await _proxy_to_litellm("/chat/completions", request)
    if isinstance(response, JSONResponse):
        return response

    try:
        await credit_service.record_completion(user, response, request.get("model"))
    except Exception as err:
        log.error("Credit accounting failed for /chat/completions: %s", err)

    return response


@router.post("/responses")
async def responses(request: dict, user=Depends(get_current_api_key_user)):
    await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)
    request["stream"] = False

    file_id = request.get("metadata", {}).get("file_id")
    if file_id:
        file = _resolve_file_or_404(file_id)
        _append_file_to_responses_input(
            request.get("input", []), file.data.get("content", "")
        )

    response = await _proxy_to_litellm("/responses", request)
    if isinstance(response, JSONResponse):
        return response

    try:
        await credit_service.record_completion(
            user,
            _responses_usage_as_chat_completion(response),
            request.get("model"),
        )
    except Exception as err:
        log.error("Credit accounting failed for /responses: %s", err)

    return response


@router.post("/files")
async def upload(request: Request, user=Depends(get_current_api_key_user)):
    try:
        form = await request.form()
        file: UploadFile = form.get("file")
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided."
            )
        file_item = upload_file(request=request, file=file, user=user)
        return JSONResponse(
            content={
                "id": file_item.id,
                "object": "file",
                "filename": file_item.filename,
                "bytes": file_item.meta.get("size"),
                "status": "processed" if not getattr(file_item, "error", None) else "error",
                "error": getattr(file_item, "error", None),
                "created_at": file_item.created_at if hasattr(file_item, "created_at") else None,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload failed." + str(exc),
        )
