import time
import logging
import sys
import os
import re
import asyncio
import io
import random
import json
import html
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor
from open_webui.utils.web_search_parser import get_inline_citations, get_used_search_queries, get_web_search_results, inject_citations_into_content, getDomain
from fastapi import Request
from starlette.responses import StreamingResponse
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.users import Users
from beyond_the_loop.models.models import ModelModel
from beyond_the_loop.prompts import (
    FILE_INTENT_DECISION_PROMPT,
    KNOWLEDGE_INTENT_DECISION_PROMPT,
    DEFAULT_RAG_IMAGE_TEMPLATE,
)
from beyond_the_loop.utils.structured_completion import (
    structured_completion,
    FileIntentDecision,
    KnowledgeUseDecision,
)
from beyond_the_loop.utils.smart_router import (
    SMART_ROUTER_MODEL,
    format_domain_label,
    select_model as smart_router_select_model,
)
from beyond_the_loop.socket.main import (
    get_event_call,
    get_event_emitter,
)
from beyond_the_loop.models.knowledge import Knowledges
from open_webui.routers.tasks import (
    generate_queries,
    generate_title,
)
from beyond_the_loop.models.users import UserModel
from beyond_the_loop.models.models import Models
from beyond_the_loop.retrieval.utils import get_sources_from_files
from beyond_the_loop.models.files import Files
from beyond_the_loop.storage.provider import Storage
# NOTE: `Loader` is deliberately NOT imported at module top. It pulls in
# langchain_text_splitters → sentence_transformers → transformers → torch,
# which added ~29s to every pod cold-start (measured with `python -X importtime`).
# It is imported lazily inside the file-loading function below, since it is
# only used on the RAG file upload path — regular chat completions never need it.
from beyond_the_loop.retrieval.loaders.main import Loader
from beyond_the_loop.routers.litellm import generate_chat_completion
from beyond_the_loop.utils.image_generation import generate_image, resolve_image_urls
from open_webui.utils.task import (
    rag_template,
)
from open_webui.utils.misc import (
    get_message_list,
    add_or_update_system_message,
    add_or_update_user_message,
    get_last_user_message,
    get_last_user_message_item,
)
from open_webui.tasks import create_task
from beyond_the_loop.config import (
    LITELLM_MODEL_CONFIG,
    LITELLM_MODEL_MAP,
)
from open_webui.env import (
    SRC_LOG_LEVELS,
    GLOBAL_LOG_LEVEL,
    ENABLE_REALTIME_CHAT_SAVE,
)
from open_webui.constants import TASKS
from beyond_the_loop.utils.chat_compression import (
    maybe_compress_chat,
    gather_and_inject_project_context,
)

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


async def chat_file_intent_decision_handler(
        form_data: dict, user: UserModel, pii_session=None
) -> tuple[dict, str]:
    """
    Decide if the attached files are needed for this turn.
    Returns (modified_body, intent) where intent is one of "RAG", "FULL", "NONE".
    On "NONE" the files are stripped from metadata so downstream handlers skip them.
    """

    files = form_data.get("metadata", {}).get("files", [])

    if not files:
        return form_data, "RAG"  # No files, downstream checks short-circuit

    # Filter out image files - only process non-image files
    non_image_files = []

    for file_item in files:
        if isinstance(file_item, dict):
            # Check if it's a regular file (not web search results or collections)
            if file_item.get("type") not in ["web_search_results", "collection"]:
                file_id = file_item.get("id")
                if file_id:
                    try:
                        file_record = Files.get_file_by_id(file_id)
                        if file_record and file_record.meta:
                            content_type = file_record.meta.get("content_type", "")
                            # Skip image files
                            if not content_type.startswith("image/"):
                                non_image_files.append(file_item)
                    except Exception as e:
                        log.debug(f"Error checking file {file_id}: {e}")
                        # If we can't determine the type, include it
                        non_image_files.append(file_item)
            else:
                # Collections and web search results should use RAG
                non_image_files.append(file_item)

    if not non_image_files:
        return form_data, "RAG"  # No non-image files, proceed with normal RAG

    # Use DEFAULT_AGENT_MODEL to decide intent
    user_message = get_last_user_message(form_data["messages"])
    if not user_message:
        return form_data, "RAG"  # No user message, proceed with RAG

    from beyond_the_loop.pii.session import anonymize_filename, pii_note_prefix
    file_name_str = ', '.join(
        anonymize_filename(f.get('name', 'unknown'), pii_session) for f in non_image_files
    )

    try:
        result = await structured_completion(
            messages=[
                {"role": "system", "content": pii_note_prefix(pii_session is not None) + FILE_INTENT_DECISION_PROMPT},
                {
                    "role": "user",
                    "content": f"User message: {user_message}\n\nFile names: {file_name_str}\n\nWhat is the user's intent?"
                }
            ],
            response_model=FileIntentDecision,
            model=Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id),
            user=user,
        )
        intent = result.intent
        log.debug(f"File intent decision: {intent}")

        if intent == "NONE":
            # Drop the files so the RAG handler, FULL extraction and
            # litellm file-upload pipeline all skip them for this turn.
            form_data.get("metadata", {}).pop("files", None)

        return form_data, intent

    except Exception as e:
        log.exception(f"Error in file intent decision: {e}")
        return form_data, "RAG"  # Fallback to RAG on error


def extract_file_content_with_loader(file_id: str) -> str:
    """
    Extract text content from a file by ID using the existing Loader system.
    """
    try:
        file_record = Files.get_file_by_id(file_id)
        if not file_record:
            return f"[File {file_id} not found]"

        # Get file path using Storage
        if file_record.path:
            try:
                storage = Storage()
                file_path = storage.get_file(file_record.path)

                # Use the existing Loader system to extract content
                from beyond_the_loop.retrieval.loaders.main import Loader
                loader = Loader()
                content_type = file_record.meta.get("content_type", "") if file_record.meta else ""

                # Load documents using the existing system
                documents = loader.load(file_record.filename, content_type, file_path)

                # Combine all document content
                combined_content = "\n\n".join([doc.page_content for doc in documents])
                return combined_content

            except Exception as e:
                log.debug(f"Error loading file {file_id} with Loader: {e}")

        # Fallback: try to get content from file data if available
        if file_record.data and 'content' in file_record.data:
            return file_record.data['content']

        return f"[Could not extract content from file {file_record.filename}]"

    except Exception as e:
        log.exception(f"Error extracting content from file {file_id}: {e}")
        return f"[Error reading file {file_id}]"


async def chat_completion_files_handler(
        request: Request, form_data: dict, user: UserModel, extra_params: dict,
        pii_active: bool = False,
) -> tuple[dict, dict[str, list]]:
    sources = []

    if files := form_data.get("metadata", {}).get("files", None):
        event_emitter = extra_params["__event_emitter__"]

        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "analyzing_results",
                    "done": False
                },
            }
        )

        try:
            queries_response = await generate_queries(
                "retrieval",
                form_data["messages"],
                form_data.get("chat_id", None),
                user,
                pii_active=pii_active,
            )

            queries = queries_response.get("queries", [])
        except Exception as e:
            queries = []

        if len(queries) == 0:
            queries = [get_last_user_message(form_data["messages"])]

        try:
            # Offload get_sources_from_files to a separate thread
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as executor:
                sources = await loop.run_in_executor(
                    executor,
                    lambda: get_sources_from_files(
                        files=files,
                        queries=queries,
                        embedding_function=lambda query: request.app.state.EMBEDDING_FUNCTION(
                            query, user=user
                        ),
                        k=request.app.state.config.TOP_K,
                        reranking_function=request.app.state.rf,
                        r=request.app.state.config.RELEVANCE_THRESHOLD
                    ),
                )

        except Exception as e:
            log.exception(e)

        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "analyzing_results",
                    "done": True
                },
            }
        )

        log.debug(f"rag_contexts:sources: {sources}")

    return form_data, {"sources": sources}


def apply_params_to_form_data(form_data):
    params = form_data.pop("params", {})

    if "seed" in params:
        form_data["seed"] = params["seed"]

    if "stop" in params:
        form_data["stop"] = params["stop"]

    if "temperature" in params:
        form_data["temperature"] = params["temperature"]

    if "max_tokens" in params:
        form_data["max_tokens"] = params["max_tokens"]

    if "top_p" in params:
        form_data["top_p"] = params["top_p"]

    if "frequency_penalty" in params:
        form_data["frequency_penalty"] = params["frequency_penalty"]

    if "reasoning_effort" in params:
        form_data["reasoning_effort"] = params["reasoning_effort"]

    return form_data


class ClientDisconnectedError(Exception):
    """Raised when the client has disconnected during request processing."""
    pass


class PIIRedactionError(Exception):
    """Raised when PII anonymization fails mid-flight. Aborts the request to
    prevent partially redacted (mixed-state) data from leaking to the LLM."""
    pass


async def check_disconnect(request):
    """Check if the client has disconnected and raise if so."""
    if await request.is_disconnected():
        raise ClientDisconnectedError("Client disconnected")


async def process_chat_payload(request, form_data, metadata, user, model: ModelModel):
    form_data = apply_params_to_form_data(form_data)

    # Remove legacy variables from form_data.
    form_data.pop("variables", None)

    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

    chat_id = metadata.get("chat_id")

    # PII redaction: anonymize all message content before ANY downstream
    # consumer (compression, smart router, RAG, LLM) sees it.
    #
    # Two client-controlled inputs:
    #   - `pii_enabled` (Mode A): master toggle. When False, no anonymization.
    #   - `pii_released_entities` (Mode B): list of original strings that
    #     should pass through verbatim even when the filter is on. Used for
    #     selective deanonymization of false positives or intentional release.
    #
    # Permission gate: if either control is "relaxed" (filter off OR releases
    # set) but the user lacks `pii.allow_disable_in_chat` (admins bypass),
    # we silently force back to safe defaults.
    pii_session = None
    filtered_user_content = None
    pii_released_entities: list = []
    pii_released_used: list = []
    if chat_id and form_data.get("messages"):
        try:
            from beyond_the_loop.pii.session import (
                PIISession,
                anonymize_messages,
                is_pii_filter_enabled,
            )
            from beyond_the_loop.prompts import PII_SYSTEM_PROMPT, PII_IMAGE_SYSTEM_PROMPT
            from beyond_the_loop.utils.access_control import has_permission

            client_pii_enabled = form_data.pop("pii_enabled", True) is not False
            client_released_raw = form_data.pop("pii_released_entities", None) or []
            client_manual_entities_raw = form_data.pop("pii_manual_entities", None) or []
            client_manual_entities = [
                str(x) for x in client_manual_entities_raw
                if isinstance(x, str) and x.strip()
            ] if isinstance(client_manual_entities_raw, list) else []
            client_released = [
                str(x) for x in client_released_raw if isinstance(x, (str, int))
            ] if isinstance(client_released_raw, list) else []

            relaxed = (not client_pii_enabled) or len(client_released) > 0
            if relaxed and user.role != "admin" and not has_permission(
                user.id, "pii.allow_disable_in_chat"
            ):
                log.warning(
                    "[pii] user %s lacks pii.allow_disable_in_chat — forcing safe defaults",
                    user.id,
                )
                client_pii_enabled = True
                client_released = []

            pii_released_entities = client_released

            if is_pii_filter_enabled(user.company_id) and client_pii_enabled:
                pii_session = PIISession(chat_id)
                for entity in client_manual_entities:
                    pii_session.register_manual(entity)
                # Surface the anonymization step in the UI — the work can
                # take a few seconds on long histories / many RAG chunks
                # under MAX_CONCURRENT_ANALYZES=1, and an unannotated spinner
                # in that window feels broken.
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "action": "anonymizing",
                            "description": "Anonymizing personal data",
                            "done": False,
                        },
                    }
                )
                try:
                    ru = anonymize_messages(
                        form_data["messages"], pii_session,
                        released=pii_released_entities, source="prompt",
                    )
                except Exception as e:
                    # Fail closed: anonymize_messages mutates messages in-place,
                    # so a mid-iteration crash leaves a mix of redacted and raw
                    # content. Abort instead of silently sending that to the LLM.
                    log.exception(f"[pii] anonymization failed mid-flight; aborting request: {e}")
                    raise PIIRedactionError(
                        "PII redaction failed — request aborted to prevent leaking "
                        "unredacted data."
                    ) from e

                pii_released_used.extend(ru)
                filtered_user_content = get_last_user_message(form_data["messages"])

                _pii_base = (
                    Models.get_model_by_id(model.base_model_id)
                    if model.base_model_id else None
                )
                _pii_model_name = _pii_base.name if _pii_base else model.name

                _pii_is_native_image_model = _pii_model_name == "Nano Banana" or _pii_model_name == "Nano Banana 2" or _pii_model_name == "Nano Banana Pro"

                form_data["messages"].insert(
                    0,
                    {
                        "role": "system",
                        "content": (
                            PII_IMAGE_SYSTEM_PROMPT
                            if _pii_is_native_image_model
                            else PII_SYSTEM_PROMPT
                        ),
                    },
                )
                # Empty description + done=true clears the status — the next
                # real step (smart router / RAG / generating_response) will
                # take over the status slot when it kicks in.
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "action": "anonymizing",
                            "description": "",
                            "done": True,
                        },
                    }
                )
        except PIIRedactionError:
            # Bubble up — the chat endpoint maps this to a 4xx for the client.
            raise
        except Exception as e:
            # Setup errors (config lookup, permission check, import failure)
            # before any in-place mutation has happened. Safe to continue without
            # the filter — no half-redacted state to worry about.
            log.exception(f"[pii] redaction setup failed, continuing WITHOUT redaction: {e}")
            pii_session = None

    try:

        if chat_id:
            # Use DEFAULT_AGENT_MODEL for compression when the selected model is a virtual
            # model (e.g. Smart Router) that has no real LiteLLM backing — otherwise
            # _generate_summary would call the LiteLLM proxy with an unknown model name
            # and hang indefinitely.
            is_smart_router = (
                model.name == SMART_ROUTER_MODEL.name
                or model.base_model_id == SMART_ROUTER_MODEL.id
            )
            compression_model = (
                Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)
                if is_smart_router
                else model
            ) or model
            form_data = await maybe_compress_chat(
                form_data=form_data,
                model=compression_model,
                chat_id=chat_id,
                event_emitter=event_emitter,
                pii_active=pii_session is not None,
                user=user,
            )
            form_data = await gather_and_inject_project_context(
                form_data=form_data,
                chat_id=chat_id,
                model=compression_model,
                event_emitter=event_emitter,
                pii_active=pii_session is not None,
                user=user,
            )
    except Exception as e:
        log.exception(f"[chat_compression] failed, continuing without compression/project context: {e}")

    log.debug(f"form_data: {form_data}")

    extra_params = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_call,
        "__user__": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
        },
        "__metadata__": metadata,
        "__request__": request,
    }

    events = []
    continue_chat_action = form_data.pop("__continue_chat_action__", None)
    if continue_chat_action:
        events.append({"type": "action", "data": continue_chat_action})
    sources = []

    features = form_data.pop("features", {}) or {}

    user_message = get_last_user_message(form_data["messages"])

    last_user_msg_item = get_last_user_message_item(form_data["messages"])
    has_image_input = isinstance(last_user_msg_item.get("content") if last_user_msg_item else None, list) and any(
        isinstance(p, dict) and p.get("type") == "image_url"
        for p in (last_user_msg_item.get("content") or [])
    )

    is_smart_router_model = model.name == SMART_ROUTER_MODEL.name
    is_smart_router_assistant = model.base_model_id == SMART_ROUTER_MODEL.id

    if (is_smart_router_model or is_smart_router_assistant) and user_message:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "smart_router",
                    "description": "Selecting the most suitable model",
                    "done": False,
                },
            }
        )

        routed_model, routing_decision, candidates_info = await smart_router_select_model(
            user_message, user, messages=form_data["messages"],
            has_image_input=has_image_input, pii_active=pii_session is not None,
        )

        # Fallback to DEFAULT_AGENT_MODEL when the router can't pick anything.
        target = routed_model or Models.get_model_by_name_and_company(
            os.getenv("DEFAULT_AGENT_MODEL"), user.company_id
        )

        if target:
            if is_smart_router_model:
                model = target
                form_data["model"] = target.id
            else:
                # Assistant: keep system prompt/params, only swap base_model_id.
                model = model.model_copy(update={"base_model_id": target.id})
            metadata["selected_model_id"] = target.id

            # Give the routed image target exactly one correct system prompt.
            # Mirrors src/lib/utils/default_prompts/image_generation.ts.
            _target_cfg = LITELLM_MODEL_CONFIG.get(target.name, {})
            if _target_cfg.get("supports_image_generation"):

                _target_is_native_image_model = target.name == "Nano Banana" or target.name == "Nano Banana 2" or target.name == "Nano Banana Pro"

                if pii_session is not None:
                    from beyond_the_loop.prompts import (
                        PII_IMAGE_SYSTEM_PROMPT,
                        PII_SYSTEM_PROMPT,
                    )
                    image_gen_system_prompt = (
                        PII_IMAGE_SYSTEM_PROMPT
                        if _target_is_native_image_model
                        else PII_SYSTEM_PROMPT + "\n\n" + 
                        "You are an image generation model. When the user requests "
                        "an image, generate one. Keep any accompanying text short."
                    )
                else:
                    image_gen_system_prompt = (
                        "You are an image generation model. When the user requests "
                        "an image, generate one. Keep any accompanying text short."
                    )
                    
                form_data["messages"] = [
                    m for m in form_data["messages"] if m.get("role") != "system"
                ]
                form_data["messages"].insert(
                    0, {"role": "system", "content": image_gen_system_prompt}
                )
            else:
                no_image_gen_guard = (
                    "You do not have access to any image generation tool. "
                    "Never emit tool calls, function calls, or raw JSON action "
                    "blocks (e.g. `dalle.text2im`, `image_generation`). If the "
                    "user requests an image, tell them you cannot create images "
                    "and offer to help in another way."
                )
                form_data["messages"].insert(
                    0, {"role": "system", "content": no_image_gen_guard}
                )

        # Propagate tool needs from routing decision into features so the
        # web_search / code_interpreter tools are actually passed to the model.
        if routing_decision:
            if "web_search" in routing_decision.required_tools:
                features["web_search"] = True
            if "code_execution" in routing_decision.required_tools or "document_creation" in routing_decision.required_tools:
                features["code_interpreter"] = True
            if "image_generation" in routing_decision.required_tools:
                features["image_generation"] = True
            if "mcp" in routing_decision.required_tools:
                features["mcp"] = True

            debug_info = {
                "required_tools": list(routing_decision.required_tools),
                "domain": format_domain_label(routing_decision.domain),
                "task_type": routing_decision.task_type,
                "complexity": routing_decision.complexity,
                "candidates": candidates_info,
            }
            metadata["smart_router_debug_data"] = debug_info
            await event_emitter({"type": "smart_router_debug_data", "data": debug_info})

        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "smart_router",
                    "description": "Selecting the most suitable model",
                    "done": True,
                    "hidden": True,
                },
            }
        )

    # Set feature flags in metadata so litellm.py can inject the correct provider-specific tools
    _model_cfg = LITELLM_MODEL_CONFIG.get(model.name, {})
    _base_model = Models.get_model_by_id(model.base_model_id)
    if _base_model:
        _model_cfg = LITELLM_MODEL_CONFIG.get(_base_model.name, {})

    # Determine if this model uses the OpenAI Responses API (which supports file uploads for code interpreter)
    _effective_model_name = _base_model.name if _base_model else model.name
    _use_responses_api = "/responses/" in LITELLM_MODEL_MAP.get(_effective_model_name, "")

    if features.get("web_search") and _model_cfg.get("supports_web_search"):
        metadata["web_search_enabled"] = True
    if _model_cfg.get("supports_image_generation"):
        metadata["image_generation_enabled"] = True
    if features.get("code_interpreter") and _model_cfg.get("supports_code_execution"):
        metadata["code_interpreter_enabled"] = True

    # MCP servers: resolve user-visible enabled servers if the model supports MCP.
    # Client may opt out of individual servers per chat via `mcp_disabled_server_ids`
    # (client-state, not persisted). Encrypted auth tokens travel through metadata;
    # decryption happens just-in-time in `litellm.py` when the provider-specific
    # payload is assembled.
    mcp_disabled_ids = set(form_data.pop("mcp_disabled_server_ids", None) or [])

    if _model_cfg.get("supports_mcp"):
        from beyond_the_loop.models.mcp_servers import MCPServers
        from beyond_the_loop.utils.access_control import has_permission as _has_perm
        from beyond_the_loop.utils.mcp_oauth import get_fresh_bearer

        if _has_perm(user.id, "workspace.mcp_connections"):
            try:
                active_servers = MCPServers.get_active_servers_for_user(user.id)
                resolved = []
                for s in active_servers:
                    if s.id in mcp_disabled_ids:
                        continue
                    # Resolve the bearer token *now* — for OAuth servers this
                    # triggers a proactive refresh if expiry is within 60s.
                    # We never put the encrypted blob into metadata; only the
                    # decrypted access token for this single request.
                    access_token = await get_fresh_bearer(s)
                    if (s.auth_type in {"bearer", "oauth"}) and not access_token:
                        # OAuth never connected, or refresh failed — skip this
                        # server rather than send a header-less MCP call that
                        # the provider would just reject.
                        log.info(
                            "[mcp] skipping %s for user %s: no usable token",
                            s.id, user.id,
                        )
                        continue
                    resolved.append({
                        "id": s.id,
                        "name": s.name,
                        "url": s.url,
                        "transport": s.transport,
                        "auth_type": s.auth_type,
                        "access_token_plain": access_token,
                        "tool_filter": s.tool_filter,
                    })
                if resolved:
                    metadata["mcp_servers_resolved"] = resolved
            except Exception as e:
                log.warning(
                    "[mcp] failed to resolve servers for user %s: %s", user.id, e
                )

    model_knowledge = Knowledges.get_knowledge_by_ids(
        [knowledge.get("id", "") for knowledge in model.meta.knowledge]) if model.meta.knowledge else None

    model_files = model.meta.files

    # Remove file duplicates and remove files from form_data, add it to metadata
    files = form_data.pop("files", [])

    flattened_files = []

    for f in files:
        if f.get("type") == "collection" and isinstance(f.get("files"), list):
            flattened_files.extend(f["files"])
        else:
            flattened_files.append(f)

    files = list({json.dumps(f, sort_keys=True): f for f in flattened_files}.values())

    metadata = {
        **metadata,
        "files": files,
    }

    form_data["metadata"] = metadata

    if model_knowledge or model_files:
        from beyond_the_loop.pii.session import anonymize_filename, pii_note_prefix
        file_names = ', '.join(
            anonymize_filename(f.get('name', ''), pii_session) for f in model_files
        ) if model_files else ''

        knowledge_names = ', '.join(
            anonymize_filename(knowledge.name, pii_session) for knowledge in model_knowledge
        ) if model_knowledge else ''

        knowledge_files = Files.get_files_by_ids([fid for k in model_knowledge for fid in (
            k.data.get("file_ids", []) if k.data else [])]) if model_knowledge else []

        knowledge_file_names = ', '.join(
            anonymize_filename(file.filename, pii_session) for file in knowledge_files
        ) if model_knowledge else ''

        await check_disconnect(request)
        knowledge_result = await structured_completion(
            messages=[
                {"role": "system", "content": pii_note_prefix(pii_session is not None) + KNOWLEDGE_INTENT_DECISION_PROMPT},
                {
                    "role": "user",
                    "content": f"User question: {user_message}\n\nKnowledge base names: {knowledge_names}, File names: {file_names}, {knowledge_file_names}\n\nDo I need this resources to answer the question?"
                }
            ],
            response_model=KnowledgeUseDecision,
            model=Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id),
            user=user,
        )
        use_model_knowledge_or_files = knowledge_result.needs_knowledge == "YES"

        if use_model_knowledge_or_files:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "knowledge_search",
                        "query": user_message,
                        "done": False,
                    },
                }
            )

            if model_knowledge:
                files.extend([
                    {
                        "type": "file",
                        "id": file.id,
                        "name": file.filename,
                        "collection_name": f"file-{file.id}",
                    }
                    for file in knowledge_files
                ])

            if model_files:
                model_file_records = Files.get_files_by_ids(
                    [f.get("id") for f in model_files if f.get("id")]
                )
                files.extend([
                    {
                        "type": "file",
                        "id": file.id,
                        "name": file.filename,
                        "collection_name": f"file-{file.id}",
                    }
                    for file in model_file_records
                ])

    # For code interpreter on OpenAI Responses API: skip RAG and text extraction entirely.
    # Files stay in metadata["files"] so litellm.py can upload them to OpenAI Files API.
    # For other providers (e.g. Gemini codeExecution), still extract file content as text
    # because those models don't support file uploads via the code interpreter path.
    #
    # Exception: when the PII filter is active we MUST NOT ship raw files to OpenAI —
    # they bypass anonymization. Force extraction so the loader runs and the content
    # gets anonymized into the prompt. The PII_SYSTEM_PROMPT (already injected above
    # whenever pii_session is set) tells the LLM that files were extracted and
    # anonymized server-side, so no separate code-interpreter notice is needed here.
    code_interpreter_enabled = form_data.get("metadata", {}).get("code_interpreter_enabled", False)
    skip_file_processing = (
        code_interpreter_enabled
        and _use_responses_api
        and pii_session is None
    )

    # First, decide if this is a RAG task or content extraction task.
    # Run the intent decision in every case (incl. assistants with a knowledge
    # base or user collections) so meta questions like "what is in the file?"
    # or "translate the document" can take the full-content path instead of a
    # vector search that returns nothing.
    if not skip_file_processing:
        try:
            form_data, file_intent = await chat_file_intent_decision_handler(
                form_data, user, pii_session=pii_session
            )
        except Exception as e:
            log.exception(f"Error in file intent decision: {e}")
            file_intent = "RAG"  # Fallback to RAG
    else:
        file_intent = "NONE"  # Skipped: code interpreter on responses API handles files directly

    await check_disconnect(request)

    if not skip_file_processing and file_intent == "RAG":
        # Proceed with normal RAG processing
        try:
            form_data, flags = await chat_completion_files_handler(
                request, form_data, user, extra_params,
                pii_active=pii_session is not None,
            )
            sources.extend(flags.get("sources", []))
        except Exception as e:
            log.exception(e)
    elif not skip_file_processing and file_intent == "FULL":
        # Handle non-RAG task: extract file content and append to user prompt.
        # Anonymize each file separately so its source is tracked per-file
        # (the sidebar groups variables by source = file name).
        if pii_session is not None:
            # The user-message anonymization status was already cleared above;
            # re-emit here so the spinner covers the (often longer) file
            # extraction + per-file anonymization phase instead of going dark.
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "anonymizing",
                        "description": "Anonymizing personal data",
                        "done": False,
                    },
                }
            )
        try:
            file_contents = []

            for file_item in files:
                if isinstance(file_item, dict):
                    file_id = file_item.get("id")
                    if file_id:
                        if file_item.get("type") == "web_search_results":
                            continue
                        # legacy
                        if file_item.get("type") == "collection":
                            if isinstance(file_id, str) and file_id.startswith("file-"):
                                file_id = file_id[5:]
                            else:
                                continue
                        try:
                            file_record = Files.get_file_by_id(file_id)
                            if file_record and file_record.meta:
                                content_type = file_record.meta.get("content_type", "")
                                # Skip image files
                                if not content_type.startswith("image/"):
                                    content = extract_file_content_with_loader(file_id)
                                    if pii_session is not None:
                                        try:
                                            content, _ru = pii_session.anonymize(
                                                content, pii_released_entities,
                                                source=f"file:{file_record.filename}",
                                            )
                                            pii_released_used.extend(_ru)
                                        except Exception:
                                            log.exception(
                                                "[pii] failed to anonymize extracted content of %s; sending unredacted",
                                                file_record.filename,
                                            )
                                    file_contents.append(
                                        f"\n\n--- Content of {file_record.filename} ---\n{content}\n--- End of {file_record.filename} ---")
                        except Exception as e:
                            log.debug(f"Error processing file {file_id}: {e}")

            # Append file contents to the last user message
            if file_contents:
                combined_content = "".join(file_contents)

                form_data["messages"] = add_or_update_user_message(
                    combined_content, form_data["messages"]
                )

                del form_data["metadata"]["files"]

        except Exception as e:
            log.exception(f"Error processing files for content extraction: {e}")
        finally:
            if pii_session is not None:
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "action": "anonymizing",
                            "description": "",
                            "done": True,
                        },
                    }
                )

    # If context is not empty, insert it into the messages (only for RAG tasks)
    if len(sources) > 0 and file_intent == "RAG":
        if pii_session is not None:
            # Re-emit the anonymization status: RAG search emitted its own
            # "searching knowledge" status above, which overwrote ours; now
            # the per-chunk anonymization runs and would otherwise be silent.
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "anonymizing",
                        "description": "Anonymizing personal data",
                        "done": False,
                    },
                }
            )
        context_string = ""
        for source_idx, source in enumerate(sources):
            source_id = source.get("name", "")

            if "snippets" in source:
                for doc_idx, doc_context in enumerate(source["snippets"]):
                    doc_source_id = source.get("file_id") or source_id 

                    # Same session as the user-message anonymization — same
                    # name in prompt and retrieved doc → same placeholder.
                    # Source IDs (filenames) intentionally not analyzed.
                    if pii_session is not None:
                        try:
                            chunk_source = doc_source_id or source_id or "unbekannt"
                            # RAG chunks coming from knowledge collections carry
                            # IDs like "file-<uuid>" — resolve to the original
                            # filename for a meaningful sidebar label.
                            resolved = chunk_source
                            try:
                                candidate = chunk_source[5:] if chunk_source.startswith("file-") else chunk_source
                                if re.fullmatch(r"[0-9a-fA-F-]{32,36}", candidate):
                                    f_rec = Files.get_file_by_id(candidate)
                                    if f_rec and f_rec.filename:
                                        resolved = f_rec.filename
                            except Exception:
                                pass
                            doc_context, _ru = pii_session.anonymize(
                                doc_context, pii_released_entities,
                                source=f"file:{resolved}",
                            )
                            pii_released_used.extend(_ru)
                        except Exception:
                            log.exception("[pii] failed to anonymize RAG chunk; sending unredacted")

                    if source_id:
                        context_string += f"<source><source_id>{doc_source_id if doc_source_id is not None else source_id}</source_id><source_context>{doc_context}</source_context></source>\n"
                    else:
                        # If there is no source_id, then do not include the source_id tag
                        context_string += f"<source><source_context>{doc_context}</source_context></source>\n"

        if pii_session is not None:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "anonymizing",
                        "description": "",
                        "done": True,
                    },
                }
            )

        context_string = context_string.strip()
        prompt = get_last_user_message(form_data["messages"])

        if prompt is None:
            raise Exception("No user message found")
        if (
                request.app.state.config.RELEVANCE_THRESHOLD == 0
                and context_string.strip() == ""
        ):
            log.debug(
                f"With a 0 relevancy threshold for RAG, the context cannot be empty"
            )

        _rag_template = (
            DEFAULT_RAG_IMAGE_TEMPLATE
            if _model_cfg.get("supports_image_generation")
            else request.app.state.config.RAG_TEMPLATE
        )
        form_data["messages"] = add_or_update_system_message(
            rag_template(_rag_template, context_string, prompt),
            form_data["messages"],
        )
    elif file_intent == "RAG" and (model_knowledge or model_files or files):
        # Retrieval ran but returned no hits. Without a notice the model would
        # answer "I don't see any file" — which confuses the user because the UI
        # just showed "searching knowledge". Instead, tell the model that the
        # file is attached but the vector search came back empty.
        log.info("[rag] no matching chunks — injecting empty-results fallback notice")
        form_data["messages"] = add_or_update_system_message(
            (
                "Knowledge search notice: A semantic search was performed over the "
                "attached document(s) / knowledge base for the user's current "
                "question, but no sufficiently relevant passages were found. The "
                "file(s) are attached and present — the search query was simply "
                "too general or semantically off (e.g. meta questions like 'What "
                "is in the file?'). Do NOT reply with 'I don't see any file' — the "
                "file is there. Instead, ask the user to be more specific or to "
                "mention a keyword / section, or proactively suggest concrete "
                "questions they could ask. Reply in the same language as the "
                "user's most recent message."
            ),
            form_data["messages"],
        )

    # If there are citations, add them to the data_items
    # Drop RAG sources whose retrieval came back empty — without this the UI
    # would still render the file as a "source" even though no snippet matched.
    def _has_identifier(s):
        return bool(s.get("name") or s.get("title") or s.get("file_id") or s.get("url"))

    def _is_empty_rag(s):
        return s.get("type") == "rag" and not s.get("snippets")

    sources = [source for source in sources if _has_identifier(source) and not _is_empty_rag(source)]

    if len(sources) > 0:
        events.append({"sources": sources})

    if model_knowledge or model_files:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "knowledge_search",
                    "query": user_message,
                    "done": True,
                    "hidden": True,
                },
            }
        )

    # Persist the session once after every anonymization pass (user message,
    # file extract, RAG) has populated the forward/reverse maps, then echo
    # the filtered user message + variable map + released list to the UI in
    # a single event. The frontend derives the badge state from the presence
    # of `variables` (filter ran) and the length of `released_entities`
    # (full vs. partial). No separate status field is sent or persisted.
    if pii_session is not None:
        try:
            pii_session.save()
            metadata["pii_session"] = pii_session
            if event_emitter:
                await event_emitter(
                    {
                        "type": "pii:user_message",
                        "data": {
                            "filtered_content": filtered_user_content,
                            "variables": dict(pii_session.forward),
                            "variable_sources": pii_session.sources_serialized(),
                            "released_entities": sorted(set(pii_released_used)),
                        },
                    }
                )
        except Exception:
            log.exception("[pii] failed to persist session / emit pii:user_message")

    return form_data, metadata, events, model


async def process_chat_response(
        request, response, form_data, user, events, metadata, tasks, model
):
    async def background_tasks_handler():
        message_map = Chats.get_messages_by_chat_id(metadata["chat_id"])
        message = message_map.get(metadata["message_id"]) if message_map else None

        if message:
            messages = get_message_list(message_map, message.get("id"))

            if tasks and messages:
                if TASKS.TITLE_GENERATION in tasks:
                    if tasks[TASKS.TITLE_GENERATION]:
                        # Messages in the DB are stored in original (user input)
                        # and deanonymized (streamed assistant response) form.
                        # If the chat has the PII filter enabled, re-anonymize
                        # before sending to the title LLM and deanonymize the
                        # returned title before persisting it.
                        pii_session = None
                        try:
                            from beyond_the_loop.pii.session import (
                                PIISession,
                                anonymize_messages,
                                is_pii_filter_enabled,
                            )
                            if is_pii_filter_enabled(user.company_id):
                                pii_session = PIISession(metadata["chat_id"])
                                anonymize_messages(messages, pii_session)
                                pii_session.save()
                        except Exception:
                            log.exception(
                                "[pii] failed to anonymize messages for title generation; aborting title task"
                            )
                            return

                        res = await generate_title(
                            request,
                            {
                                "model": message["model"],
                                "messages": messages,
                                "chat_id": metadata["chat_id"],
                                "pii_active": pii_session is not None,
                            },
                            user,
                        )

                        if res and isinstance(res, dict):
                            title = res.get("title", "") or messages[0].get("content", "New chat")
                            if pii_session is not None:
                                try:
                                    title = pii_session.deanonymize(title)
                                except Exception:
                                    log.exception("[pii] failed to deanonymize generated title")
                            Chats.update_chat_title_by_id(metadata["chat_id"], title)

                            await event_emitter(
                                {
                                    "type": "chat:title",
                                    "data": title,
                                }
                            )
                    elif len(messages) == 2:
                        title = messages[0].get("content", "New chat")

                        Chats.update_chat_title_by_id(metadata["chat_id"], title)

                        await event_emitter(
                            {
                                "type": "chat:title",
                                "data": message.get("content", "New chat"),
                            }
                        )

    event_emitter = None
    event_caller = None

    if (
            "session_id" in metadata
            and metadata["session_id"]
            and "chat_id" in metadata
            and metadata["chat_id"]
            and "message_id" in metadata
            and metadata["message_id"]
    ):
        event_emitter = get_event_emitter(metadata)
        event_caller = get_event_call(metadata)

    # Non-streaming response
    if not isinstance(response, StreamingResponse):
        if (
            isinstance(response, dict)
            and metadata.get("selected_model_id")
            and "selectedModelId" not in response
        ):
            response["selectedModelId"] = metadata["selected_model_id"]

        if event_emitter:
            selected_model_id = response.get("selectedModelId") or response.get("selected_model_id")
            if selected_model_id:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "selectedModelId": selected_model_id,
                    },
                )

            if response.get("choices", [])[0].get("message", {}).get("content"):
                content = response["choices"][0]["message"]["content"]

                if content:

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": response,
                        }
                    )

                    title = Chats.get_chat_title_by_id(metadata["chat_id"])

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": {
                                "done": True,
                                "content": content,
                                "title": title,
                            },
                        }
                    )

                    # Save message in the database
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            "content": content,
                        },
                    )

                    await background_tasks_handler()

            return response
        else:
            return response

    # Non standard response
    if not any(
            content_type in response.headers["Content-Type"]
            for content_type in ["text/event-stream", "application/x-ndjson"]
    ):
        return response

    # Streaming response
    if event_emitter and event_caller:
        message_update = {"model": model.id}
        if metadata.get("selected_model_id"):
            message_update["selectedModelId"] = metadata["selected_model_id"]

        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            message_update,
        )

        # Handle as a background task
        async def post_response_handler(response, events):
            def serialize_content_blocks(content_blocks, raw=False):
                content = ""

                for block in content_blocks:
                    if block["type"] == "text":
                        content = f"{content}{block['content'].strip()}\n"
                    elif block["type"] == "reasoning":
                        reasoning_display_content = "\n".join(
                            (f"> {line}" if not line.startswith(">") else line)
                            for line in block["content"].splitlines()
                        )

                        reasoning_duration = block.get("duration", None)

                        if reasoning_duration is not None:
                            if raw:
                                content = f'{content}\n<{block["tag"]}>{block["content"]}</{block["tag"]}>\n'
                            else:
                                content = f'{content}\n<details type="reasoning" done="true" duration="{reasoning_duration}">\n<summary>Thought for {reasoning_duration} seconds</summary>\n{reasoning_display_content}\n</details>\n'
                        else:
                            if raw:
                                content = f'{content}\n<{block["tag"]}>{block["content"]}</{block["tag"]}>\n'
                            else:
                                content = f'{content}\n<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n{reasoning_display_content}\n</details>\n'

                    else:
                        block_content = str(block["content"]).strip()
                        content = f"{content}{block['type']}: {block_content}\n"

                return content.strip()

            def format_reasoning_content(text):
                """Adds \n after each ** Pair in Reasoning Summaries, to adjust for Litellms OpenAI Formatting. Can hopefully be removed in future LiteLLM Updates"""
                return text.replace("**", " \n>\n>**").replace(" \n>\n>**\n>", "**\n>")

            def tag_content_handler(content_type, tags, content, content_blocks):
                end_flag = False

                def extract_attributes(tag_content):
                    """Extract attributes from a tag if they exist."""
                    attributes = {}
                    if not tag_content:  # Ensure tag_content is not None
                        return attributes
                    # Match attributes in the format: key="value" (ignores single quotes for simplicity)
                    matches = re.findall(r'(\w+)\s*=\s*"([^"]+)"', tag_content)
                    for key, value in matches:
                        attributes[key] = value
                    return attributes

                if content_blocks[-1]["type"] == "text":
                    for tag in tags:
                        # Match start tag e.g., <tag> or <tag attr="value">
                        start_tag_pattern = rf"<{tag}(\s.*?)?>"
                        match = re.search(start_tag_pattern, content)
                        if match:
                            attr_content = (
                                match.group(1) if match.group(1) else ""
                            )  # Ensure it's not None
                            attributes = extract_attributes(
                                attr_content
                            )  # Extract attributes safely

                            # Capture everything before and after the matched tag
                            before_tag = content[
                                : match.start()
                            ]  # Content before opening tag
                            after_tag = content[
                                match.end():
                            ]  # Content after opening tag

                            # Text block should contain only what came BEFORE the start tag
                            content_blocks[-1]["content"] = before_tag

                            if not content_blocks[-1]["content"]:
                                content_blocks.pop()

                            # Append the new block
                            content_blocks.append(
                                {
                                    "type": content_type,
                                    "tag": tag,
                                    "attributes": attributes,
                                    "content": "",
                                    "started_at": time.time(),
                                }
                            )

                            if after_tag:
                                # Check if the end tag is already in after_tag
                                # (start + end arrived in the same streaming chunk)
                                end_tag_pattern_inline = rf"</{tag}>"
                                if re.search(end_tag_pattern_inline, after_tag):
                                    end_tag_regex_inline = re.compile(end_tag_pattern_inline, re.DOTALL)
                                    split_inline = end_tag_regex_inline.split(after_tag, maxsplit=1)
                                    block_content_inline = split_inline[0].strip()
                                    leftover_inline = split_inline[1].strip() if len(split_inline) > 1 else ""

                                    if block_content_inline:
                                        content_blocks[-1]["content"] = block_content_inline
                                        content_blocks[-1]["ended_at"] = time.time()
                                        content_blocks[-1]["duration"] = int(
                                            content_blocks[-1]["ended_at"] - content_blocks[-1]["started_at"]
                                        )
                                    else:
                                        content_blocks.pop()

                                    content_blocks.append({"type": "text", "content": leftover_inline})

                                    # Clean the accumulated content string so subsequent calls
                                    # don't re-detect the already-processed tags
                                    content = re.sub(
                                        rf"<{tag}(.*?)>(.|\n)*?</{tag}>",
                                        "",
                                        content,
                                        flags=re.DOTALL,
                                    )

                                    end_flag = True
                                else:
                                    content_blocks[-1]["content"] = after_tag

                            break
                elif content_blocks[-1]["type"] == content_type:
                    tag = content_blocks[-1]["tag"]
                    # Match end tag e.g., </tag>
                    end_tag_pattern = rf"</{tag}>"

                    # Check if the content has the end tag
                    if re.search(end_tag_pattern, content):
                        end_flag = True

                        block_content = content_blocks[-1]["content"]
                        # Strip start and end tags from the content
                        start_tag_pattern = rf"<{tag}(.*?)>"
                        block_content = re.sub(
                            start_tag_pattern, "", block_content
                        ).strip()

                        end_tag_regex = re.compile(end_tag_pattern, re.DOTALL)
                        split_content = end_tag_regex.split(block_content, maxsplit=1)

                        # Content inside the tag
                        block_content = (
                            split_content[0].strip() if split_content else ""
                        )

                        # Leftover content (everything after `</tag>`)
                        leftover_content = (
                            split_content[1].strip() if len(split_content) > 1 else ""
                        )

                        if block_content:
                            content_blocks[-1]["content"] = block_content
                            content_blocks[-1]["ended_at"] = time.time()
                            content_blocks[-1]["duration"] = int(
                                content_blocks[-1]["ended_at"]
                                - content_blocks[-1]["started_at"]
                            )

                            # Reset the content_blocks by appending a new text block
                            if content_type != "code_interpreter":
                                if leftover_content:
                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": leftover_content,
                                        }
                                    )
                                else:
                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": "",
                                        }
                                    )

                        else:
                            # Remove the block if content is empty
                            content_blocks.pop()

                            if leftover_content:
                                content_blocks.append(
                                    {
                                        "type": "text",
                                        "content": leftover_content,
                                    }
                                )
                            else:
                                content_blocks.append(
                                    {
                                        "type": "text",
                                        "content": "",
                                    }
                                )

                        # Clean processed content
                        content = re.sub(
                            rf"<{tag}(.*?)>(.|\n)*?</{tag}>",
                            "",
                            content,
                            flags=re.DOTALL,
                        )

                return content, content_blocks, end_flag

            message = Chats.get_message_by_id_and_message_id(
                metadata["chat_id"], metadata["message_id"]
            )

            content = message.get("content", "") if message else ""
            content_blocks = [
                {
                    "type": "text",
                    "content": content,
                }
            ]
            anonymized_content_snapshot = ""
            response_images = []
            used_search_queries = []

            pending_image_call = None
            pending_image_index = None

            sources = None  # Store sources from the LLMs ("citations") at this scope

            # We might want to disable this by default
            detect_reasoning = True

            reasoning_tags = [
                "think",
                "thinking",
                "reason",
                "reasoning",
                "thought",
                "Thought",
            ]

            await event_emitter(
                {
                    "type": "chat:completion",
                    "data": message_update,
                }
            )

            try:
                for event in events:
                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": event,
                        }
                    )

                    # Save message in the database
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {
                            **event,
                        },
                    )

                async def stream_body_handler(response):
                    nonlocal content
                    nonlocal content_blocks
                    nonlocal response_images
                    nonlocal anonymized_content_snapshot
                    nonlocal used_search_queries
                    nonlocal pending_image_call
                    nonlocal pending_image_index

                    pending_image_call = None
                    pending_image_index = None

                    generating_response = True

                    # PII deanonymizer: buffers chunks so placeholders split across
                    # SSE boundaries aren't leaked as "[[PER". None = pass-through.
                    # Gated by the same per-company feature flag as the payload hook.
                    pii_deanonymizer = None
                    try:
                        _chat_id_for_pii = metadata.get("chat_id")
                        if _chat_id_for_pii:
                            from beyond_the_loop.pii.session import (
                                PIISession,
                                is_pii_filter_enabled,
                            )
                            if is_pii_filter_enabled(user.company_id):
                                pii_deanonymizer = PIISession(_chat_id_for_pii).streaming_deanonymizer()
                    except Exception as e:
                        log.exception(f"[pii] failed to init streaming deanonymizer: {e}")

                    async for line in response.body_iterator:
                        line = line.decode("utf-8") if isinstance(line, bytes) else line
                        data = line

                        # Skip empty lines
                        if not data.strip():
                            continue

                        # "data:" is the prefix for each event
                        if not data.startswith("data:"):
                            continue

                        # Remove the prefix
                        data = data[len("data:"):].strip()

                        try:
                            data = json.loads(data)

                            if data.get("id") and generating_response:
                                await event_emitter(
                                    {
                                        "type": "status",
                                        "data": {
                                            "action": "generating_response",
                                            "done": True,
                                        },
                                    }
                                )

                                generating_response = False
                            nonlocal sources
                            if "search_results" in data and sources is None or sources is [] :
                                perplexity_sources = []
                                for search_result in data.get("search_results") or []:
                                    perplexity_sources.append({
                                        "type": "web_search",
                                        "title": search_result.get("title"),
                                        "url": search_result.get("url"),
                                        "domain": getDomain(search_result.get("url")),
                                        "snippet": "",
                                    })
                                sources = perplexity_sources

                            if "status_event" in data:
                                await event_emitter(
                                    {
                                        "type": "status",
                                        "data": data["status_event"],
                                    }
                                )
                                continue

                            if "code_execution_event" in data:
                                await event_emitter(
                                    {
                                        "type": "source",
                                        "data": {
                                            "type": "code_execution",
                                            **data["code_execution_event"],
                                        },
                                    }
                                )
                                continue

                            if "file_refs" in data:
                                await event_emitter(
                                    {
                                        "type": "file_refs",
                                        "data": data["file_refs"],
                                    }
                                )

                                if "content_replacement" in data:
                                    content = data["content_replacement"]
                                    content_blocks.clear()
                                    content_blocks.append(
                                        {"type": "text", "content": content}
                                    )
                                continue

                            if "selected_model_id" in data:
                                model_id = data["selected_model_id"]
                                Chats.upsert_message_to_chat_by_id_and_message_id(
                                    metadata["chat_id"],
                                    metadata["message_id"],
                                    {
                                        "selectedModelId": model_id,
                                    },
                                )
                            else:
                                choices = data.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})

                                delta_images = delta.get("images", None)

                                if delta_images:
                                    if (
                                        content_blocks
                                        and content_blocks[-1]["type"] == "reasoning"
                                        and content_blocks[-1].get("attributes", {}).get("type") == "reasoning_content"
                                        and "duration" not in content_blocks[-1]
                                    ):
                                        reasoning_block = content_blocks[-1]
                                        reasoning_block["ended_at"] = time.time()
                                        reasoning_block["duration"] = int(
                                            reasoning_block["ended_at"]
                                            - reasoning_block["started_at"]
                                        )

                                    for delta_image in delta_images:
                                        image_base64 = delta_image['image_url']["url"]

                                        response_images.append({"type": "image", "url": image_base64})
                                for dtc in delta.get("tool_calls") or []:
                                    func = dtc.get("function", {})
                                    idx = dtc.get("index")

                                    if func.get("name") == "generate_image":
                                        pending_image_index = idx
                                        pending_image_call = {
                                            "id": dtc.get("id"),
                                            "args": "",
                                        }

                                    if (
                                        pending_image_call is not None
                                        and idx == pending_image_index
                                        and func.get("arguments")
                                    ):
                                        pending_image_call["args"] += func["arguments"]

                                    if func.get("name") == "web_search":
                                        pending_search_index = idx
                                        pending_search_args = ""

                                    if idx == pending_search_index and func.get("arguments"):
                                        pending_search_args += func["arguments"]
                                        try:
                                            query = json.loads(pending_search_args).get("query", "")
                                            await event_emitter({
                                                "type": "status",
                                                "data": {
                                                    "action": "web_search",
                                                    "done": False,
                                                    "description": 'Searching "{{searchQuery}}"',
                                                    "query": query,
                                                },
                                            })
                                            used_search_queries.append(query)
                                            if content_blocks[-1].get("content") != '': # Claude doesn't add \n after web_search event 
                                                content_blocks.append(
                                                        {
                                                            "type": "text",
                                                            "content": "",
                                                        }
                                                    )
                                                await event_emitter(
                                                    {
                                                        "type": "chat:completion",
                                                        "data": {
                                                            "content": serialize_content_blocks(
                                                                content_blocks
                                                            )
                                                        },
                                                    }
                                                )
                                            pending_search_index = None  # fertig, nicht nochmal feuern
                                        except json.JSONDecodeError:
                                            pass  # arguments noch unvollständig, weiter 

                                reasoning_content = (
                                        delta.get("reasoning_content")
                                        or delta.get("reasoning")
                                        or delta.get("thinking")
                                )

                                if reasoning_content:
                                    if (
                                            not content_blocks
                                            or content_blocks[-1]["type"] != "reasoning"
                                    ):
                                        reasoning_block = {
                                            "type": "reasoning",
                                            "attributes": {
                                                "type": "reasoning_content"
                                            },
                                            "content": "",
                                            "started_at": time.time(),
                                        }
                                        content_blocks.append(reasoning_block)
                                    else:
                                        reasoning_block = content_blocks[-1]

                                    reasoning_block["content"] += reasoning_content

                                    data = {
                                        "content": format_reasoning_content(serialize_content_blocks(
                                            content_blocks
                                        )),
                                        "type": "reasoning",
                                    }
                                if used_search_queries == []:
                                    used_search_queries = get_used_search_queries(delta, data)

                                web_search_results = get_web_search_results(delta, data)
                                for search_result in web_search_results:
                                    if sources is None:
                                        sources = []
                                    sources.append({
                                            "type": "web_search",
                                            "title": search_result.title,
                                            "url": search_result.url,
                                            "domain": search_result.domain,
                                            "snippet": "",
                                            "queries": used_search_queries,
                                    })
                                if web_search_results:
                                    await event_emitter({
                                        "type": "chat:completion",
                                        "data": {
                                            "sources": sources,
                                        },
                                    })
                                    await event_emitter({                                                                                                                                                                              
                                        "type": "status",
                                        "data": {
                                            "action": "web_search", 
                                            "done": True,
                                        }
                                    }) 

                                inline_citations = get_inline_citations(delta, data, sources)
                                for inline_citation in inline_citations:
                                    content_blocks, delta = inject_citations_into_content(
                                        inline_citation,
                                        content_blocks,
                                        delta,
                                        pii_session=metadata.get("pii_session"),
                                        anonymized_text=anonymized_content_snapshot
                                    )
                                if inline_citations:
                                    last_text_block = next(
                                        (b for b in reversed(content_blocks) if b.get("type") == "text"),
                                        None,
                                    )
                                    if re.search(r'\(\[([^\]]+)\]\(([^)]+)\)\)', last_text_block["content"]): # remove chatgpt markdown citations
                                        last_text_block["content"] = re.sub(r'\(\[([^\]]+)\]\(([^)]+)\)\)', '', last_text_block["content"]) 
                                    elif re.search(r'\[([^\]]+)\]\(([^)]+)\)', last_text_block["content"]):
                                        last_text_block["content"] = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', '', last_text_block["content"])
                                    await event_emitter(
                                        {
                                            "type": "chat:completion",
                                            "data": {
                                                "content": serialize_content_blocks(
                                                    content_blocks
                                                )
                                            },
                                        }
                                    )

                                value = delta.get("content")
                                if value:
                                    anonymized_content_snapshot += value
                                if value and pii_deanonymizer is not None:
                                    value = pii_deanonymizer.feed(value)

                                if value:
                                    content = f"{content}{value}"
                                    if (
                                            content_blocks
                                            and content_blocks[-1]["type"]
                                            == "reasoning"
                                            and content_blocks[-1]
                                            .get("attributes", {})
                                            .get("type")
                                            == "reasoning_content"
                                    ):
                                        reasoning_block = content_blocks[-1]
                                        reasoning_block["ended_at"] = time.time()
                                        reasoning_block["duration"] = int(
                                            reasoning_block["ended_at"]
                                            - reasoning_block["started_at"]
                                        )

                                        content_blocks.append(
                                            {
                                                "type": "text",
                                                "content": "",
                                            }
                                        )

                                    if not content_blocks:
                                        content_blocks.append(
                                            {
                                                "type": "text",
                                                "content": "",
                                            }
                                        )

                                    content_blocks[-1]["content"] = (
                                            content_blocks[-1]["content"] + value
                                    )

                                    if detect_reasoning:
                                        content, content_blocks, _ = (
                                            tag_content_handler(
                                                "reasoning",
                                                reasoning_tags,
                                                content,
                                                content_blocks,
                                            )
                                        )

                                    if ENABLE_REALTIME_CHAT_SAVE:
                                        # Save message in the database
                                        Chats.upsert_message_to_chat_by_id_and_message_id(
                                            metadata["chat_id"],
                                            metadata["message_id"],
                                            {
                                                "content": serialize_content_blocks(
                                                    content_blocks
                                                ),
                                            },
                                        )
                                    elif (content_blocks[-1][
                                              "type"] == "reasoning"):  # In case reasoning summary was detected in tag_content_handler
                                        data = {
                                            "content": serialize_content_blocks(
                                                content_blocks
                                            ),
                                            "type": "reasoning",
                                        }
                                    else:
                                        data = {
                                            "content": serialize_content_blocks(
                                                content_blocks
                                            ),
                                            "type": "text",
                                            "added_content": value,
                                        }

                            await event_emitter(
                                {
                                    "type": "chat:completion",
                                    "data": data,
                                }
                            )
                        except Exception as e:
                            done = "data: [DONE]" in line
                            if done:
                                pass
                            else:
                                log.debug("Error: ", e)
                                continue

                    # Flush any remainder left in the deanonymizer buffer (e.g. a
                    # placeholder that started but never closed). This is emitted
                    # as a final chunk so the client never loses content.
                    if pii_deanonymizer is not None:
                        try:
                            remainder = pii_deanonymizer.flush()
                            if remainder:
                                content = f"{content}{remainder}"
                                if not content_blocks:
                                    content_blocks.append({"type": "text", "content": ""})
                                content_blocks[-1]["content"] = (
                                    content_blocks[-1]["content"] + remainder
                                )
                                await event_emitter({
                                    "type": "chat:completion",
                                    "data": {
                                        "content": serialize_content_blocks(content_blocks),
                                        "type": "text",
                                        "added_content": remainder,
                                    },
                                })
                        except Exception as e:
                            log.exception(f"[pii] flush failed: {e}")

                    if content_blocks:
                        # Clean up the last text block
                        if content_blocks[-1]["type"] == "text":
                            content_blocks[-1]["content"] = content_blocks[-1][
                                "content"
                            ].strip()

                            if not content_blocks[-1]["content"]:
                                content_blocks.pop()

                                if not content_blocks:
                                    content_blocks.append(
                                        {
                                            "type": "text",
                                            "content": "",
                                        }
                                    )

                    if response.background:
                        await response.background()

                await stream_body_handler(response)

                MAX_IMAGE_ROUNDS = 10
                image_rounds = 0

                while pending_image_call is not None and image_rounds < MAX_IMAGE_ROUNDS:
                    image_rounds += 1
                    call = pending_image_call
                    pending_image_call = None  # consumed; reset before reinvoke

                    try:
                        image_args = json.loads(call["args"] or "{}")
                    except json.JSONDecodeError:
                        image_args = {}

                    input_urls = resolve_image_urls(
                        image_args.get("input_image_indices", []),
                        form_data["messages"],
                    )

                    await event_emitter({
                        "type": "status",
                        "data": {
                            "action": "generating_image",
                            "done": False,
                            "description": "Generating image…",
                        },
                    })

                    data_uri, image_error = await generate_image(
                        image_args.get("prompt", ""),
                        image_args.get("size", "auto"),
                        input_urls,
                    )

                    await event_emitter({
                        "type": "status",
                        "data": {"action": "generating_image", "done": True},
                    })

                    if data_uri:
                        response_images.append({"type": "image", "url": data_uri})

                    form_data["messages"].append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": "generate_image",
                                "arguments": call["args"] or "{}",
                            },
                        }],
                    })
                    form_data["messages"].append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": image_error
                        or "Image generated successfully and shown to the user.",
                    })

                    response, _ = await generate_chat_completion(
                        form_data, user, model
                    )
                    await stream_body_handler(response)

                for block in content_blocks:
                    if block.get("type") == "text" and "sandbox:/mnt/data/" in block.get("content", ""):
                        block["content"] = re.sub(
                            r'\(sandbox:/mnt/data/([^)]+)\)',
                            r'(unavailable://\1)',
                            block["content"]
                        )
                    # Strip internal [Image N] reference markers for image gen models
                    if block.get("type") == "text" and "content" in block:
                        block["content"] = re.sub(
                            r'\s*\[Image \d+\]', '', block["content"]
                        )

                title = Chats.get_chat_title_by_id(metadata["chat_id"])

                data = {
                    "done": True,
                    "content": serialize_content_blocks(content_blocks),
                    "title": title,
                }

                if response_images:
                    data["files"] = response_images

                if not ENABLE_REALTIME_CHAT_SAVE:
                    # Save message in the database
                    message = {
                        "content": serialize_content_blocks(content_blocks),
                    }
                    if sources:  # Use the stored sources
                        message["sources"] = sources

                        await event_emitter({
                            "type": "chat:completion",
                            "data": {
                                "sources": sources,
                            },
                        })

                    if response_images:
                        message["files"] = response_images

                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        message
                    )

                await event_emitter(
                    {
                        "type": "chat:completion",
                        "data": data,
                    }
                )

                await background_tasks_handler()
            except asyncio.CancelledError:
                log.warning("Task was cancelled!")
                await event_emitter({"type": "task-cancelled"})

                if not ENABLE_REALTIME_CHAT_SAVE:
                    # Save message in the database
                    message = {
                        "content": serialize_content_blocks(content_blocks),
                    }
                    if sources:  # Use the stored sources‚
                        message["sources"] = sources

                        await event_emitter({
                            "type": "chat:completion",
                            "data": {
                                "sources": sources,
                            },
                        })

                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        message
                    )

                raise
            except Exception as e:
                # Catches unhandled errors during streaming (e.g. asyncio.TimeoutError from
                # aiohttp when OpenAI's code interpreter exceeds AIOHTTP_CLIENT_TIMEOUT).
                # Without this, the background task dies silently and the frontend is left
                # showing "Writing code" / spinner forever because no done event is emitted.
                log.exception(f"Unhandled error in streaming response: {e}")

                await event_emitter(
                    {
                        "type": "chat:completion",
                        "data": {
                            "done": True,
                            "content": serialize_content_blocks(content_blocks),
                            "error": {"content": str(e)},
                        },
                    }
                )

                if not ENABLE_REALTIME_CHAT_SAVE:
                    message = {
                        "content": serialize_content_blocks(content_blocks),
                        "error": {"content": str(e)},
                    }
                    if sources:
                        message["sources"] = sources
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        message
                    )

            if response.background is not None:
                await response.background()

        # background_tasks.add_task(post_response_handler, response, events)
        # Wrap so we can log the actual streaming duration end-to-end.
        # `post_response_handler` runs in a background task, so this fires
        # long after the HTTP request has already returned.
        stream_started = time.perf_counter()

        async def _timed_post_response_handler():
            outcome = "ok"
            try:
                await post_response_handler(response, events)
            except Exception:
                outcome = "error"
                raise
            finally:
                log.info(
                    "chat stream ended",
                    extra={
                        "event": "chat_stream_end",
                        "model": getattr(model, "name", None),
                        "model_id": getattr(model, "id", None),
                        "chat_id": metadata.get("chat_id"),
                        "user_id": metadata.get("user_id"),
                        "duration_ms": round((time.perf_counter() - stream_started) * 1000, 2),
                        "outcome": outcome,
                    },
                )

        task_id, _ = create_task(_timed_post_response_handler())
        return {"status": True, "task_id": task_id}

    else:
        # Fallback to the original response
        async def stream_wrapper(original_generator, events):
            def wrap_item(item):
                return f"data: {item}\n\n"

            for event in events:
                yield wrap_item(json.dumps(event))

            async for data in original_generator:
                yield data

        return StreamingResponse(
            stream_wrapper(response.body_iterator, events),
            headers=dict(response.headers),
            background=response.background,
        )
