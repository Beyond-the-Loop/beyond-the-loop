import hashlib
import io
import json
import logging
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Optional

import aiohttp
import requests
import os

from aiohttp import ClientResponseError
from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.responses import FileResponse, StreamingResponse, Response
from starlette.background import BackgroundTask
from openai import OpenAI
from beyond_the_loop.models.models import Models


from beyond_the_loop.config import (
    CACHE_DIR,
    LITELLM_MODEL_MAP,
)
from beyond_the_loop.prompts import COMPLETION_ERROR_MESSAGE_PROMPT, MAGIC_PROMPT_SYSTEM
from open_webui.env import (
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST,
    ENABLE_FORWARD_USER_INFO_HEADERS,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS


from open_webui.utils.payload import (
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)

from open_webui.utils.auth import get_verified_user, get_current_api_key_user
from beyond_the_loop.utils.access_control import has_access
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.services.fair_model_usage_service import fair_model_usage_service
from beyond_the_loop.socket.main import get_event_emitter

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OPENAI"])

##########################################
#
# Utility functions
#
##########################################

session: aiohttp.ClientSession | None = None

async def _get_session() -> aiohttp.ClientSession:
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            read_bufsize=10 * 1024 * 1024,  # 10 MB
            connector=aiohttp.TCPConnector(
                limit=200,
                enable_cleanup_closed=True, # proactively detects stale connections
                ttl_dns_cache=300,  # cache Docker DNS for 5 min
            )
        )
    return session

async def send_get_request(url, key=None):
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as s:
            async with s.get(
                url, headers={**({"Authorization": f"Bearer {key}"} if key else {})}
            ) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        log.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse]
):
    if response:
        response.close()


async def _upload_files_to_openai(files: list) -> list:
    """Upload files to Azure OpenAI Files API for code_interpreter and return file IDs."""
    from beyond_the_loop.models.files import Files
    from beyond_the_loop.storage.provider import Storage

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        return []

    file_ids = []
    s = await _get_session()

    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        nested = file_item.get("file")
        file_id = file_item.get("id") or (nested.get("id") if isinstance(nested, dict) else None)
        if not file_id:
            continue

        try:
            file_record = Files.get_file_by_id(file_id)
            if not file_record or not file_record.path:
                continue

            local_path = Storage.get_file(file_record.path)
            filename = os.path.basename(local_path)

            with open(local_path, "rb") as f:
                file_content = f.read()

            url = f"{endpoint}/openai/v1/files?api-version=preview"
            form = aiohttp.FormData()
            form.add_field("purpose", "assistants")
            form.add_field("file", file_content, filename=filename, content_type="application/octet-stream")
            async with s.post(url, data=form, headers={"api-key": api_key}) as r:
                if r.status in (200, 201):
                    result = await r.json()
                    openai_file_id = result.get("id")

                    if openai_file_id:
                        file_ids.append(openai_file_id)
                else:
                    log.warning(f"File upload returned {r.status}: {await r.text()}")

        except Exception as e:
            log.warning(f"Failed to upload file {file_id} to OpenAI: {e}")

    return file_ids


async def _download_and_store_container_file(
    container_id: str,
    openai_file_id: str,
    filename: str,
    user_id: str,
) -> Optional[str]:
    """Download a container file from OpenAI and store it in our Files API. Returns internal file ID or None on failure."""
    from beyond_the_loop.models.files import FileForm, Files
    from beyond_the_loop.storage.provider import Storage

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        return None

    url = f"{endpoint}/openai/v1/containers/{container_id}/files/{openai_file_id}/content?api-version=preview"
    s = await _get_session()
    async with s.get(url, headers={"api-key": api_key}) as r:
        if r.status != 200:
            log.warning(f"Failed to download container file {openai_file_id}: {r.status} {await r.text()}")
            return None
        content = await r.read()

    internal_id = str(uuid.uuid4())
    storage_filename = f"{internal_id}_{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    _, file_path = Storage.upload_file(io.BytesIO(content), storage_filename)
    Files.insert_new_file(
        user_id,
        FileForm(
            id=internal_id,
            filename=filename,
            path=file_path,
            meta={
                "name": filename,
                "content_type": content_type,
                "size": len(content),
            },
        ),
    )
    return internal_id


##########################################
#
# Model management functions
#
##########################################

async def get_all_models_from_litellm():
    """
    Fetch all available models from the litellm server.
    Returns the models in OpenAI API format.
    """
    try:
        url = f"{os.getenv('OPENAI_API_BASE_URL')}/models"
        api_key = os.getenv('OPENAI_API_KEY')
        
        log.info(f"Fetching models from litellm server: {url}")

        response = await send_get_request(url, api_key)
        
        if response is None:
            log.error("Failed to fetch models from litellm server")
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch models from litellm server"
            )
        
        log.info(f"Successfully fetched {len(response.get('data', []))} models from litellm")
        return response
        
    except Exception as e:
        log.error(f"Error fetching models from litellm: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching models: {str(e)}"
        )

##########################################
#
# API routes
#
##########################################

router = APIRouter()

@router.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    try:
        body = await request.body()
        name = hashlib.sha256(body).hexdigest()

        SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
        SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
        file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

        # Check if the file already exists in the cache
        if file_path.is_file():
            return FileResponse(file_path)

        r = None
        try:
            r = requests.post(
                url=f"{os.getenv('OPENAI_API_BASE_URL')}/audio/speech",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    **(
                        {
                            "X-OpenWebUI-User-Name": user.first_name + " " + user.last_name,
                            "X-OpenWebUI-User-Id": user.id,
                            "X-OpenWebUI-User-Email": user.email,
                            "X-OpenWebUI-User-Role": user.role,
                        }
                        if ENABLE_FORWARD_USER_INFO_HEADERS
                        else {}
                    ),
                },
                stream=True,
            )

            r.raise_for_status()

            # Save the streaming content to a file
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(file_body_path, "w") as f:
                json.dump(json.loads(body.decode("utf-8")), f)

            # Return the saved file
            return FileResponse(file_path)

        except Exception as e:
            log.exception(e)

            detail = None
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        detail = f"External: {res['error']}"
                except Exception:
                    detail = f"External: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=detail if detail else "Server Connection Error",
            )

    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)


async def generate_chat_completion(
        form_data: dict,
        user,
        model
):
    payload = {**form_data}
    metadata = payload.pop("metadata", {})

    event_emitter = get_event_emitter(metadata)

    agent_or_task_prompt = metadata.get("agent_or_task_prompt", False)

    if not agent_or_task_prompt:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "generating_response",
                    "done": False,
                    "description": "Preparing model request"
                },
            }
        )

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found. Please check the model ID is correct.",
        )

    has_chat_id = "chat_id" in metadata and metadata["chat_id"] is not None

    if model.base_model_id:
        if model.user_id == "system" and model.meta.is_kickstart_assistant is None:
            model_name = model.base_model_id
        else:
            base_model = Models.get_model_by_id(model.base_model_id)
            if base_model is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Base model '{model.base_model_id}' not found for assistant '{model.name}'.",
                )
            model_name = base_model.name
    else:
        model_name = model.name

    payload["model"] = model_name

    # GPT-5.4 (and other azure/responses/* models) must go through /v1/responses
    # so that code interpreter annotations (container_id, file_id) are not dropped.
    use_responses_api = "/responses/" in LITELLM_MODEL_MAP.get(model_name, "")

    tools = []

    if metadata.get("web_search_enabled", False):
        if use_responses_api:
            tools.append({"type": "web_search_preview"})
        else:
            payload["web_search_options"] = {}

    if metadata.get("image_generation_enabled", False):
        if use_responses_api:
            tools.append({"type": "image_generation"})

    if metadata.get("code_interpreter_enabled", False):
        if use_responses_api:
            file_ids = await _upload_files_to_openai(metadata.get("files", []))
            container = {"type": "auto"}
            if file_ids:
                container["file_ids"] = file_ids
            tools.append({"type": "code_interpreter", "container": container})
        else:
            tools.append({"codeExecution": {}})

    if tools:
        payload["tools"] = tools

    subscription = payments_service.get_subscription(user.company_id)

    if has_chat_id or agent_or_task_prompt:
        await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

    params = model.params.model_dump()
    payload = apply_model_params_to_body_openai(params, payload)
    payload = apply_model_system_prompt_to_body(params, payload, metadata, user)

    # Check model access
    if not agent_or_task_prompt and not(
        model.is_active and (user.id == model.user_id or (not model.base_model_id and user.role == "admin") or has_access(
            user.id, type="read", access_control=model.access_control
        ))
    ):
        raise HTTPException(
            status_code=403,
            detail="Model not found, no access for user",
        )

    # Check model fair usage
    if not agent_or_task_prompt and (subscription.get("plan") == "free" or subscription.get("plan") == "premium"):
        fair_model_usage_service.check_for_fair_model_usage(user, payload["model"], subscription.get("plan"))

    if use_responses_api:
        payload.pop("stream_options", None)

        # Responses API uses "input" instead of "messages", and requires
        # different content block types than Chat Completions. The text type
        # is role-dependent: user/system → input_text, assistant → output_text.
        # Assistant messages only accept output_text / refusal — images from
        # prior turns (e.g. generated by another model) get stripped from the
        # assistant message and forwarded to the next user message, so the
        # current model can still see them.
        #   image_url  → input_image  (flat string, not nested)
        def _convert_content_for_responses_api(content, role):
            is_assistant = role == "assistant"
            text_type = "output_text" if is_assistant else "input_text"
            if isinstance(content, str):
                return [{"type": text_type, "text": content}]
            if not isinstance(content, list):
                return content
            converted = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    converted.append({"type": text_type, "text": block["text"]})
                elif btype == "image_url":
                    if is_assistant:
                        continue
                    url = block.get("image_url", {}).get("url", "")
                    converted.append({"type": "input_image", "image_url": url})
                else:
                    if is_assistant:
                        continue
                    converted.append(block)
            return converted

        def _extract_assistant_images(content):
            if not isinstance(content, list):
                return []
            images = []
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "image_url":
                    continue
                url = block.get("image_url", {}).get("url", "")
                if url:
                    images.append({"type": "input_image", "image_url": url})
            return images

        messages = payload.pop("messages")
        input_items = []
        carried_images = []

        for msg in messages:
            role = msg.get("role")
            original_content = msg.get("content") if "content" in msg else None

            if role in ("user", "assistant", "system") and original_content is not None:
                msg["content"] = _convert_content_for_responses_api(original_content, role)

            if role == "user" and carried_images:
                if isinstance(msg.get("content"), list):
                    msg["content"] = carried_images + msg["content"]
                else:
                    msg["content"] = carried_images
                carried_images = []

            input_items.append(msg)

            if role == "assistant":
                carried_images.extend(_extract_assistant_images(original_content))

        # If the conversation ends on an assistant turn with images, flush them
        # as a standalone user message so they are not lost.
        if carried_images:
            input_items.append({"role": "user", "content": carried_images})

        payload["input"] = input_items
    elif payload["stream"]:
        payload["stream_options"] = {"include_usage": True}

    # Convert the modified body back to JSON
    payload = json.dumps(payload)

    r = None
    streaming = False
    response = None

    try:
        if not agent_or_task_prompt:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "generating_response",
                        "done": False,
                        "description": "Creating session"
                    },
                }
            )

        s = await _get_session()

        if not agent_or_task_prompt:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "generating_response",
                        "done": False,
                        "description": "Waiting for model response"
                    },
                }
            )

        api_url = (
            f"{os.getenv('OPENAI_API_BASE_URL')}/responses"
            if use_responses_api
            else f"{os.getenv('OPENAI_API_BASE_URL')}/chat/completions"
        )

        r = await s.request(
            method="POST",
            url=api_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "Content-Type": "application/json",
                **(
                    {
                        "X-OpenWebUI-User-Name": user.first_name + " " + user.last_name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS
                    else {}
                ),
            },
        )

        # Check if response is SSE
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True

            if use_responses_api:
                async def responses_api_stream():
                    buffer = ""
                    event_type = None
                    response_id = f"chatcmpl-responses-{int(time.time())}"
                    annotations = []
                    accumulated_content = ""
                    code_accumulator = {}
                    log_all_until_completed = False
                    web_search_active = False
                    last_web_search_status = None

                    async for chunk in r.content:
                        chunk_str = chunk.decode("utf-8", errors="replace")
                        buffer += chunk_str

                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.rstrip("\r")

                            if line.startswith("event: "):
                                event_type = line[7:].strip()
                            elif line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    yield b"data: [DONE]\n\n"
                                    return
                                try:
                                    data = json.loads(data_str)
                                    event = data.get("type") or event_type or ""

                                    if event == "response.reasoning_summary_text.delta":
                                        delta = data.get("delta", "")
                                        if delta:
                                            think_chunk = {
                                                "id": response_id,
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": model_name,
                                                "choices": [{"index": 0, "delta": {"thinking": delta}, "finish_reason": None}],
                                            }
                                            yield f"data: {json.dumps(think_chunk)}\n\n".encode()

                                    elif event in (
                                        "response.web_search_call.in_progress",
                                        "response.web_search_call.searching",
                                        "response.web_search_call.completed",
                                    ):
                                        # Redundant with output_item.added/done — skip to avoid status flicker.
                                        pass

                                    elif event == "response.output_item.added":
                                        item = data.get("item", {})
                                        if item.get("type") == "web_search_call":
                                            web_search_active = True
                                            last_web_search_status = {
                                                "action": "web_search",
                                                "done": False,
                                                "description": "Searching the web",
                                            }
                                            yield f"data: {json.dumps({'status_event': last_web_search_status})}\n\n".encode()

                                    elif event == "response.code_interpreter_call.in_progress":
                                        yield f"data: {json.dumps({'status_event': {'action': 'analyzing_results', 'done': False, 'description': 'Writing code'}})}\n\n".encode()

                                    elif event == "response.code_interpreter_call_code.delta":
                                        item_id = data.get("item_id", "")
                                        delta = data.get("delta", "")
                                        if item_id and delta:
                                            code_accumulator[item_id] = code_accumulator.get(item_id, "") + delta

                                    elif event == "response.code_interpreter_call_code.done":
                                        item_id = data.get("item_id", "")
                                        code = data.get("code") or code_accumulator.get(item_id, "")
                                        yield f"data: {json.dumps({'status_event': {'action': 'analyzing_results', 'done': True, 'description': 'Writing code'}})}\n\n".encode()
                                        yield f"data: {json.dumps({'status_event': {'action': 'analyzing_results', 'done': False, 'description': 'Running code'}})}\n\n".encode()
                                        if code:
                                            yield f"data: {json.dumps({'code_execution_event': {'id': item_id, 'name': 'Code', 'code': code, 'language': 'python'}})}\n\n".encode()

                                    elif event == "response.code_interpreter_call.interpreting":
                                        yield f"data: {json.dumps({'status_event': {'action': 'analyzing_results', 'done': False, 'description': 'Running code'}})}\n\n".encode()

                                    elif event == "response.code_interpreter_call.completed":
                                        item_id = data.get("item_id", "")
                                        code = code_accumulator.get(item_id, "")
                                        log_all_until_completed = True
                                        yield f"data: {json.dumps({'status_event': {'action': 'analyzing_results', 'done': True, 'description': 'Running code'}})}\n\n".encode()
                                        if item_id:
                                            yield f"data: {json.dumps({'code_execution_event': {'id': item_id, 'name': 'Code', 'code': code, 'language': 'python', 'result': {'output': ' '}}})}\n\n".encode()
                                        yield f"data: {json.dumps({'status_event': {'action': 'generating_response', 'done': True}})}\n\n".encode()

                                    elif event == "response.output_item.done":
                                        item = data.get("item", {})
                                        if item.get("type") == "web_search_call":
                                            action = item.get("action", {})
                                            action_type = action.get("type")
                                            if action_type == "search":
                                                query = action.get("query") or (action.get("queries") or [""])[0]
                                                last_web_search_status = {
                                                    "action": "web_search",
                                                    "done": False,
                                                    "description": 'Searching "{{searchQuery}}"',
                                                    "query": query,
                                                }
                                            elif action_type == "open_page":
                                                url = action.get("url", "")
                                                last_web_search_status = {
                                                    "action": "web_search",
                                                    "done": False,
                                                    "description": 'Opening "{{searchQuery}}"',
                                                    "query": url,
                                                }
                                            else:
                                                last_web_search_status = {
                                                    "action": "web_search",
                                                    "done": False,
                                                    "description": "Searching the web",
                                                }
                                            yield f"data: {json.dumps({'status_event': last_web_search_status})}\n\n".encode()

                                    elif event == "response.output_text.delta":
                                        delta = data.get("delta", "")
                                        if delta:
                                            if web_search_active and last_web_search_status is not None:
                                                web_search_active = False
                                                final_status = {**last_web_search_status, "done": True}
                                                yield f"data: {json.dumps({'status_event': final_status})}\n\n".encode()
                                            accumulated_content += delta
                                            chat_chunk = {
                                                "id": response_id,
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": model_name,
                                                "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                                            }
                                            yield f"data: {json.dumps(chat_chunk)}\n\n".encode()

                                    elif event == "response.output_text.annotation.added":
                                        annotation = data.get("annotation", {})
                                        if annotation.get("type") == "container_file_citation":
                                            annotations.append(annotation)

                                    elif event == "response.completed":
                                        log_all_until_completed = False
                                        resp = data.get("response", {})
                                        usage = resp.get("usage", {})
                                        usage_openai_format = {
                                            "model": model_name,
                                            "usage": {
                                                "prompt_tokens": usage.get("input_tokens", 0),
                                                "completion_tokens": usage.get("output_tokens", 0),
                                                "total_tokens": usage.get("total_tokens", usage.get("input_tokens", 0) + usage.get("output_tokens", 0)),
                                            }
                                        }
                                        await credit_service.record_completion(
                                            user, usage_openai_format, model_name,
                                            assistant=model.name if model.base_model_id else None,
                                            agent_or_task_prompt=agent_or_task_prompt,
                                            subscription=subscription,
                                            should_subtract_credits=has_chat_id,
                                        )
                                        if annotations:
                                            replaced_content = accumulated_content
                                            file_refs = []
                                            for a in annotations:
                                                a_filename = a.get("filename", "")
                                                a_container_id = a.get("container_id", "")
                                                a_openai_file_id = a.get("file_id", "")
                                                if not (a_filename and a_container_id and a_openai_file_id):
                                                    continue
                                                internal_id = await _download_and_store_container_file(
                                                    a_container_id, a_openai_file_id, a_filename, user.id
                                                )
                                                if internal_id:
                                                    our_url = f"/api/v1/files/{internal_id}/content/{a_filename}"
                                                    replaced_content = replaced_content.replace(
                                                        f"(sandbox:/mnt/data/{a_filename})",
                                                        f"({our_url})",
                                                    )
                                                    file_refs.append({
                                                        "file_id": internal_id,
                                                        "filename": a_filename,
                                                        "url": our_url,
                                                    })
                                                else:
                                                    fallback_url = f"/openai/container-files/{a_container_id}/{a_openai_file_id}?filename={a_filename}"
                                                    replaced_content = replaced_content.replace(
                                                        f"(sandbox:/mnt/data/{a_filename})",
                                                        f"({fallback_url})",
                                                    )
                                                    file_refs.append({
                                                        "container_id": a_container_id,
                                                        "file_id": a_openai_file_id,
                                                        "filename": a_filename,
                                                    })
                                            yield f"data: {json.dumps({'file_refs': file_refs, 'content_replacement': replaced_content})}\n\n".encode()
                                        stop_chunk = {
                                            "id": response_id,
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model_name,
                                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                                            **usage_openai_format,
                                        }
                                        yield f"data: {json.dumps(stop_chunk)}\n\n".encode()
                                        yield b"data: [DONE]\n\n"
                                        return
                                except json.JSONDecodeError as e:
                                    log.warning(f"RESPONSES API JSON decode error: {e} for: {data_str!r}")
                            elif line == "":
                                event_type = None

                return StreamingResponse(
                    responses_api_stream(),
                    status_code=r.status,
                    headers=dict(r.headers),
                    background=BackgroundTask(cleanup_response, response=r),
                ), model

            async def insert_completion_if_streaming_is_done():
                async for chunk in r.content:
                    chunk_str = chunk.decode()
                    if chunk_str.startswith('data: '):
                        try:
                            data = json.loads(chunk_str[6:])
                            if data.get('usage'):
                                # End of stream
                                # Add completion to completion table if it's a chat message from the user
                                await credit_service.record_completion(
                                    user, data, model_name,
                                    assistant=model.name if model.base_model_id else None,
                                    agent_or_task_prompt=agent_or_task_prompt,
                                    subscription=subscription,
                                    should_subtract_credits=has_chat_id,
                                )
                        except json.JSONDecodeError:
                            log.debug(f"JSON decode error for chunk: {chunk_str}")

                    yield chunk

            return StreamingResponse(
                insert_completion_if_streaming_is_done(),
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(cleanup_response, response=r),
            ), model
        else:
            try:
                response = await r.json()
            except Exception as e:
                log.error(f"Error parsing JSON response: {e}")
                response = await r.text()

            try:
                r.raise_for_status()
            except ClientResponseError as e:
                log.error(f"HTTP error from LLM backend: {e}")
                if agent_or_task_prompt:
                    raise e

                model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

                form_data = {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": COMPLETION_ERROR_MESSAGE_PROMPT
                        },
                        {
                            "role": "user",
                            "content": str(response)
                        }],
                    "stream": False,
                    "metadata": {
                        "chat_id": None,
                        "agent_or_task_prompt": True
                    },
                    "temperature": 0.0
                }

                return await generate_chat_completion(form_data, user, model)

            await credit_service.record_completion(
                user, response, model_name,
                assistant=model.name if model.base_model_id else None,
                agent_or_task_prompt=agent_or_task_prompt,
                subscription=subscription,
                should_subtract_credits=has_chat_id,
            )

            return response, model
    except Exception as e:
        log.error(f"Error in generate_chat_completion: {e}")

        detail = None
        if isinstance(response, dict):
            if "error" in response:
                detail = f"{response['error']['message'] if 'message' in response['error'] else response['error']}"
        elif isinstance(response, str):
            detail = response

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail if detail else "Server Connection Error",
        )
    finally:
        if not streaming:
            if r and isinstance(r, aiohttp.ClientResponse):
                r.close()

@router.post("/magicPrompt")
async def generate_prompt(form_data: dict, user=Depends(get_verified_user)):
    model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": MAGIC_PROMPT_SYSTEM
            },
            {
                "role": "user",
                "content": form_data["prompt"]
            }
        ],
        "stream": False,
        "metadata": {
            "chat_id": None,
            "agent_or_task_prompt": True
        },
        "temperature": 0.0
    }

    message, _ = await generate_chat_completion(payload, user, model)

    return message['choices'][0]['message']['content']