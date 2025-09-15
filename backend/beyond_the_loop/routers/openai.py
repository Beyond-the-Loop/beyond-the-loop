import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import aiohttp
import requests

import os

from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from beyond_the_loop.utils import magic_prompt_util
from beyond_the_loop.models.models import Models
from beyond_the_loop.models.completions import Completions
from beyond_the_loop.models.completions import calculate_saved_time_in_seconds

from beyond_the_loop.config import (
    CACHE_DIR,
)
from beyond_the_loop.config import DEFAULT_AGENT_MODEL
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

from open_webui.utils.auth import get_verified_user
from beyond_the_loop.utils.access_control import has_access
from beyond_the_loop.services.credit_service import CreditService

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OPENAI"])

##########################################
#
# Utility functions
#
##########################################


async def send_get_request(url, key=None):
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(
                url, headers={**({"Authorization": f"Bearer {key}"} if key else {})}
            ) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        log.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    if response:
        response.close()
    if session:
        await session.close()


##########################################
#
# API routes
#
##########################################

router = APIRouter()

@router.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    idx = None
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
                    "Authorization": f"Bearer {os.getenv("OPENAI_API_KEY")}",
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
                detail=detail if detail else "Open WebUI: Server Connection Error",
            )

    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)


@router.post("/chat/completions")
async def generate_chat_completion(
    form_data: dict,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
    agent_prompt: Optional[bool] = False
):
    payload = {**form_data}
    metadata = payload.pop("metadata", None)

    model_info = Models.get_model_by_id(form_data.get("model"))

    if model_info is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found. Please check the model ID is correct.",
        )

    has_chat_id = "chat_id" in metadata and metadata["chat_id"] is not None

    if model_info.base_model_id:
        model_name = Models.get_model_by_id(model_info.base_model_id).name
    else:
        model_name = model_info.name

    payload["model"] = model_name

    if model_name == "Mistral Large 2":
        payload["stream"] = False

    credit_service = CreditService()

    if has_chat_id or agent_prompt:
        await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

    params = model_info.params.model_dump()
    payload = apply_model_params_to_body_openai(params, payload)
    payload = apply_model_system_prompt_to_body(params, payload, metadata, user)

    if not (
        model_info.is_active and (user.id == model_info.user_id or (not model_info.base_model_id and user.role == "admin") or has_access(
            user.id, type="read", access_control=model_info.access_control
        ))
    ):
        raise HTTPException(
            status_code=403,
            detail="Model not found, no access for user",
        )

    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}

    # Convert the modified body back to JSON
    payload = json.dumps(payload)

    r = None
    session = None
    streaming = False
    response = None

    # Parse payload once for both streaming and non-streaming cases
    payload_dict = json.loads(payload)
    last_user_message = next((msg['content'] for msg in reversed(payload_dict['messages']) 
                            if msg['role'] == 'user'), '')

    try:
        session = aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
        )

        r = await session.request(
            method="POST",
            url=f"{os.getenv("OPENAI_API_BASE_URL")}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {os.getenv("OPENAI_API_KEY")}",
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

            async def insert_completion_if_streaming_is_done():
                full_response = ""
                async for chunk in r.content:
                    chunk_str = chunk.decode()
                    if chunk_str.startswith('data: '):
                        try:
                            data = json.loads(chunk_str[6:])
                            delta = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if delta:  # Only use it if there's actual content
                                full_response += delta
                            elif data.get('usage'):
                                # End of stream
                                # Add completion to completion table if it's a chat message from the user
                                if has_chat_id:
                                    input_tokens = data.get('usage', {}).get('prompt_tokens', 0)
                                    output_tokens = data.get('usage', {}).get('completion_tokens', 0)

                                    # Safely access nested dictionary values
                                    completion_tokens_details = data.get('usage', {}).get(
                                        'completion_tokens_details', {})
                                    reasoning_tokens = 0
                                    if completion_tokens_details is not None:
                                        reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)

                                    with_search_query_cost = "Perplexity" in model_name

                                    credit_cost = await credit_service.subtract_credits_by_user_and_tokens(user, model_name, input_tokens, output_tokens, reasoning_tokens, with_search_query_cost)

                                    Completions.insert_new_completion(user.id, metadata["chat_id"], model_name, credit_cost, calculate_saved_time_in_seconds(last_user_message, full_response))
                        except json.JSONDecodeError:
                            print(f"\n{chunk_str}")
                    yield chunk

            return StreamingResponse(
                insert_completion_if_streaming_is_done(),
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(
                    cleanup_response, response=r, session=session
                ),
            )
        else:
            try:
                response = await r.json()
            except Exception as e:
                log.error(e)
                response = await r.text()

            r.raise_for_status()

            if has_chat_id:
                # Add completion to completion table
                response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')

                input_tokens = response.get('usage', {}).get('prompt_tokens', 0)
                output_tokens = response.get('usage', {}).get('completion_tokens', 0)

                # Safely access nested dictionary values
                completion_tokens_details = response.get('usage', {}).get('completion_tokens_details', {})
                reasoning_tokens = 0
                if completion_tokens_details is not None:
                    reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)

                with_search_query_cost = "Perplexity" in model_name

                credit_cost = await credit_service.subtract_credits_by_user_and_tokens(user, model_name, input_tokens, output_tokens, reasoning_tokens, with_search_query_cost)

                Completions.insert_new_completion(user.id, metadata["chat_id"], model_name, credit_cost, calculate_saved_time_in_seconds(last_user_message, response_content))

            return response
    except Exception as e:
        log.exception(e)

        detail = None
        if isinstance(response, dict):
            if "error" in response:
                detail = f"{response['error']['message'] if 'message' in response['error'] else response['error']}"
        elif isinstance(response, str):
            detail = response

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail if detail else "Open WebUI: Server Connection Error",
        )
    finally:
        if not streaming and session:
            if r:
                r.close()
            await session.close()

@router.post("/magicPrompt")
async def generate_prompt(request: Request, form_data: dict, user=Depends(get_verified_user)):
    messages = magic_prompt_util.generate_magic_prompt_messages(form_data["prompt"])

    model = Models.get_model_by_name_and_company(DEFAULT_AGENT_MODEL.value, user.company_id)

    form_data = {
        "model": model.id,
        "messages": messages,
        "stream": False,
        "metadata": {"chat_id": None},
        "temperature": 0.0
    }

    message = await generate_chat_completion(request, form_data, user, None, True)

    extracted_prompt_template = magic_prompt_util.extract_prompt(message.get('choices', [{}])[0].get('message', {}).get('content', ''))

    floating_variables = magic_prompt_util.find_free_floating_variables(extracted_prompt_template)

    if len(floating_variables) > 0:

        form_data = {
            "model": model.id,
            "messages": [{'role': "user", "content": magic_prompt_util.remove_floating_variables_prompt.replace("{$PROMPT}", extracted_prompt_template)}],
            "stream": False,
            "metadata": {"chat_id": None},
            "temperature": 0.0
        }

        message = await generate_chat_completion(request, form_data, user, None, True)

        extracted_prompt_template = message.get('choices', [{}])[0].get('message', {}).get('content', '')

    return extracted_prompt_template