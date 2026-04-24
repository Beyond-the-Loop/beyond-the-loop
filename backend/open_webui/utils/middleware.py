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
import ast
from concurrent.futures import ThreadPoolExecutor
from fastapi import Request
from starlette.responses import StreamingResponse
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.users import Users
from beyond_the_loop.models.models import ModelModel
from beyond_the_loop.prompts import (
    FILE_INTENT_DECISION_PROMPT,
    KNOWLEDGE_INTENT_DECISION_PROMPT,
    SMART_ROUTER_PROMPT,
)
from beyond_the_loop.utils.structured_completion import (
    structured_completion,
    FileIntentDecision,
    KnowledgeUseDecision,
    SmartRouterDecision,
)
from beyond_the_loop.socket.main import (
    get_event_call,
    get_event_emitter,
    get_active_status_by_user_id,
)
from beyond_the_loop.models.knowledge import Knowledges
from beyond_the_loop.models.models import ModelMeta, ModelParams
from open_webui.routers.tasks import (
    generate_queries,
    generate_title,
)
from open_webui.utils.webhook import post_webhook
from beyond_the_loop.models.users import UserModel
from beyond_the_loop.models.models import Models
from beyond_the_loop.retrieval.utils import get_sources_from_files
from beyond_the_loop.routers.litellm import generate_chat_completion
from beyond_the_loop.models.files import Files
from beyond_the_loop.storage.provider import Storage
from beyond_the_loop.retrieval.loaders.main import Loader
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
from beyond_the_loop.utils.chat_compression import maybe_compress_chat

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


async def chat_file_intent_decision_handler(
        form_data: dict, user: UserModel
) -> tuple[dict, bool]:
    """
    Decide if the user's intent is RAG (search/query) or translation/content extraction.
    Returns (modified_body, is_rag_task)
    """

    files = form_data.get("metadata", {}).get("files", [])

    if not files:
        return form_data, True  # No files, proceed normally

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
        return form_data, True  # No non-image files, proceed with normal RAG

    # Use DEFAULT_AGENT_MODEL to decide intent
    user_message = get_last_user_message(form_data["messages"])
    if not user_message:
        return form_data, True  # No user message, proceed with RAG

    try:
        result = await structured_completion(
            messages=[
                {"role": "system", "content": FILE_INTENT_DECISION_PROMPT},
                {
                    "role": "user",
                    "content": f"User message: {user_message}\n\nFile names: {', '.join([f.get('name', 'unknown') for f in non_image_files])}\n\nWhat is the user's intent?"
                }
            ],
            response_model=FileIntentDecision,
            model=Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)
        )
        is_rag_task = result.intent == "RAG"
        log.debug(f"File intent decision: {result.intent} -> is_rag_task: {is_rag_task}")

        return form_data, is_rag_task

    except Exception as e:
        log.exception(f"Error in file intent decision: {e}")
        return form_data, True  # Fallback to RAG on error


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
        request: Request, form_data: dict, user: UserModel, extra_params: dict
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
                user
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
                        r=request.app.state.config.RELEVANCE_THRESHOLD,
                        hybrid_search=request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
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


async def check_disconnect(request):
    """Check if the client has disconnected and raise if so."""
    if await request.is_disconnected():
        raise ClientDisconnectedError("Client disconnected")


SMART_ROUTER_MODEL = ModelModel(
    id="Smart Router",
    name="Smart Router",
    meta=ModelMeta(),
    params=ModelParams(),
    is_active=True,
    updated_at=int(time.time()),
    created_at=int(time.time()),
    user_id=None,
    company_id="",
    base_model_id=None,
    access_control=None,
)


async def _smart_router_model_selection(
    user_message: str, user, messages: list[dict] | None = None, has_image_input: bool = False
) -> tuple[ModelModel | None, SmartRouterDecision | None]:
    """
    Score the user message complexity (1–5) via structured completion, then pick
    the best model from all candidates whose intelligence_score >= that score.
    Among qualifying models, rank by efficiency: costFactor (60%, lower=better)
    + speed (40%, higher=better), both normalized 0-1 within the candidate set.
    Returns (None, None) if no suitable model can be found.
    """
    try:
        agent_model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)

        # Build conversation context from the last few turns so follow-up messages
        # like "ja bitte" (agreeing to a suggested web search) are routed correctly.
        context_section = ""
        if messages:
            prior = [
                m for m in messages
                if m.get("role") in ("user", "assistant")
            ][:-1][-3:]
            if prior:
                lines = []
                for m in prior:
                    content = m.get("content", "")
                    if isinstance(content, list):
                        content = next(
                            (p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"),
                            "",
                        )
                    label = "User" if m.get("role") == "user" else "Assistant"
                    lines.append(f"{label}: {str(content)[:400]}")
                context_section = "### Recent Conversation:\n" + "\n".join(lines) + "\n\n"

        prompt = (
            SMART_ROUTER_PROMPT
            .replace("{{CONVERSATION_CONTEXT}}", context_section)
            .replace("{{USER_MESSAGE}}", user_message)
        )

        decision = await structured_completion(
            messages=[{"role": "user", "content": prompt}],
            response_model=SmartRouterDecision,
            model=agent_model,
        )

        target_score = max(1.0, min(5.0, decision.intelligence_score))

        # Lazy import to avoid circular dependency (main.py imports middleware.py)
        from open_webui.main import get_active_models

        active_models_result = await get_active_models(user=user)

        routable_models = [
            m for m in active_models_result["data"]
            if m.base_model_id is None  # no assistants
               and m.name != SMART_ROUTER_MODEL.name  # not Smart Router itself
               and m.is_active  # active (e.g. not locked in free plan)
               and not getattr(m, "fair_usage_limit_reached", False)  # fair usage not exhausted
        ]

        # Filter to models meeting the minimum intelligence requirement and required capabilities
        candidates = []

        for m in routable_models:
            cfg = LITELLM_MODEL_CONFIG.get(m.name, {})
            score = cfg.get("intelligence_score")
            if score is None or score < target_score:
                continue
            if decision.needs_web_search and not cfg.get("supports_web_search", False):
                continue
            if decision.needs_code_execution and not cfg.get("supports_code_execution", False):
                continue
            if decision.needs_image_generation and not cfg.get("supports_image_generation", False):
                continue
            if has_image_input and not cfg.get("supports_image_input", False):
                continue
            candidates.append(m)

        # If no candidates passed the intelligence filter, fall back to capability-only matching.
        # Capability is a hard requirement; intelligence score is a soft preference.
        if not candidates:
            needs_capability = (
                decision.needs_web_search
                or decision.needs_code_execution
                or decision.needs_image_generation
                or has_image_input
            )
            if needs_capability:
                for m in routable_models:
                    cfg = LITELLM_MODEL_CONFIG.get(m.name, {})
                    if decision.needs_web_search and not cfg.get("supports_web_search", False):
                        continue
                    if decision.needs_code_execution and not cfg.get("supports_code_execution", False):
                        continue
                    if decision.needs_image_generation and not cfg.get("supports_image_generation", False):
                        continue
                    if has_image_input and not cfg.get("supports_image_input", False):
                        continue
                    candidates.append(m)

        if not candidates:
            return None, decision

        # Build efficiency score from costFactor (60%, lower=better) and speed (40%, higher=better)
        cost_values = {
            m.name: LITELLM_MODEL_CONFIG.get(m.name, {}).get("costFactor")
            for m in candidates
        }

        speed_values = {
            m.name: LITELLM_MODEL_CONFIG.get(m.name, {}).get("speed")
            for m in candidates
        }

        valid_costs = [v for v in cost_values.values() if v is not None]
        valid_speeds = [v for v in speed_values.values() if v is not None]

        min_cost, max_cost = (min(valid_costs), max(valid_costs)) if valid_costs else (None, None)
        min_speed, max_speed = (min(valid_speeds), max(valid_speeds)) if valid_speeds else (None, None)

        def efficiency_score(model_name: str) -> float:
            cost = cost_values.get(model_name)
            speed = speed_values.get(model_name)

            cost_score = None

            if cost is not None and min_cost is not None and max_cost is not None:
                if max_cost == min_cost:
                    cost_score = 1.0
                else:
                    cost_score = 1.0 - (cost - min_cost) / (max_cost - min_cost)

            speed_score = None

            if speed is not None and min_speed is not None and max_speed is not None:
                if max_speed == min_speed:
                    speed_score = 1.0
                else:
                    speed_score = (speed - min_speed) / (max_speed - min_speed)

            if cost_score is not None and speed_score is not None:
                return 0.6 * cost_score + 0.4 * speed_score
            elif cost_score is not None:
                return cost_score
            elif speed_score is not None:
                return speed_score
            return 0.0

        scored_candidates = sorted(
            candidates, key=lambda m: efficiency_score(m.name), reverse=True
        )

        top_candidates = scored_candidates[:3]
        best_model = random.choice(top_candidates)

        return best_model, decision
    except Exception as e:
        log.exception(f"Smart Router model selection failed: {e}")
        return None, None


async def process_chat_payload(request, form_data, metadata, user, model: ModelModel):
    form_data = apply_params_to_form_data(form_data)

    # Remove variables and tool_ids from form_data. They're legacy
    form_data.pop("variables", None)
    form_data.pop("tool_ids", None)

    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

    chat_id = metadata.get("chat_id")

    # PII redaction: anonymize all message content before ANY downstream
    # consumer (compression, smart router, RAG, LLM) sees it. Gated by the
    # per-company feature flag `privacy.pii_filter_enabled` (default: ON).
    if chat_id and form_data.get("messages"):
        try:
            from beyond_the_loop.pii.session import (
                PII_SYSTEM_PROMPT,
                PIISession,
                anonymize_messages,
                is_pii_filter_enabled,
            )

            if is_pii_filter_enabled(user.company_id):
                pii_session = PIISession(chat_id)
                anonymize_messages(form_data["messages"], pii_session)
                pii_session.save()

                # Echo the filtered user message back to the frontend so the
                # UI can show "what was actually sent to the LLM" via an info
                # icon on the user message bubble. Only emit when the filter
                # actually changed the content.
                try:
                    filtered_user_content = get_last_user_message(form_data["messages"])
                    if filtered_user_content and event_emitter:
                        await event_emitter(
                            {
                                "type": "pii:user_message",
                                "data": {"filtered_content": filtered_user_content},
                            }
                        )
                except Exception:
                    log.exception("[pii] failed to emit pii:user_message event")

                form_data["messages"].insert(
                    0, {"role": "system", "content": PII_SYSTEM_PROMPT}
                )
        except Exception as e:
            log.exception(f"[pii] redaction failed, continuing WITHOUT redaction: {e}")

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
            )
    except Exception as e:
        log.exception(f"[chat_compression] failed, continuing without compression: {e}")

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
    sources = []

    features = form_data.pop("features", {}) or {}
    auto_tools = form_data.pop("auto_tools", None)

    # When auto selection is active the frontend sends features={} and auto_tools=[...].
    # Merge auto_tools into features so the rest of the pipeline sees the same structure.
    if isinstance(auto_tools, list):
        for tool in auto_tools:
            features[tool] = True

    user_message = get_last_user_message(form_data["messages"])

    last_user_msg_item = get_last_user_message_item(form_data["messages"])
    has_image_input = isinstance(last_user_msg_item.get("content") if last_user_msg_item else None, list) and any(
        isinstance(p, dict) and p.get("type") == "image_url"
        for p in (last_user_msg_item.get("content") or [])
    )

    if model.name == SMART_ROUTER_MODEL.name and user_message:
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

        routed_model, routing_decision = await _smart_router_model_selection(
            user_message, user, messages=form_data["messages"], has_image_input=has_image_input
        )

        if routed_model:
            model = routed_model
            form_data["model"] = routed_model.id
        else:
            # Fallback: smart router couldn't select a model — use DEFAULT_AGENT_MODEL
            model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)
            form_data["model"] = model.id

        # Propagate tool needs from routing decision into features so the
        # web_search / code_interpreter tools are actually passed to the model.
        if routing_decision:
            if routing_decision.needs_web_search:
                features["web_search"] = True
            if routing_decision.needs_code_execution:
                features["code_interpreter"] = True
            if routing_decision.needs_image_generation:
                features["image_generation"] = True

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

    elif model.base_model_id == SMART_ROUTER_MODEL.id and user_message:
        # Assistant whose base model is "Smart Router": run routing but keep the
        # assistant's system prompt and params by only swapping out base_model_id.
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

        routed_model, routing_decision = await _smart_router_model_selection(
            user_message, user, messages=form_data["messages"], has_image_input=has_image_input
        )

        if routed_model:
            model = model.model_copy(update={"base_model_id": routed_model.id})
        else:
            fallback = Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)
            if fallback:
                model = model.model_copy(update={"base_model_id": fallback.id})

        if routing_decision:
            if routing_decision.needs_web_search:
                features["web_search"] = True
            if routing_decision.needs_code_execution:
                features["code_interpreter"] = True

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
    if features.get("image_generation") and _model_cfg.get("supports_image_generation"):
        metadata["image_generation_enabled"] = True
    if features.get("code_interpreter") and _model_cfg.get("supports_code_execution"):
        metadata["code_interpreter_enabled"] = True

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
        file_names = ', '.join([f.get('name', '') for f in model_files]) if model_files else ''

        knowledge_names = ', '.join([knowledge.name for knowledge in model_knowledge]) if model_knowledge else ''

        knowledge_files = Files.get_files_by_ids([fid for k in model_knowledge for fid in (
            k.data.get("file_ids", []) if k.data else [])]) if model_knowledge else []

        knowledge_file_names = ', '.join(file.filename for file in knowledge_files) if model_knowledge else ''

        await check_disconnect(request)
        knowledge_result = await structured_completion(
            messages=[
                {"role": "system", "content": KNOWLEDGE_INTENT_DECISION_PROMPT},
                {
                    "role": "user",
                    "content": f"User question: {user_message}\n\nKnowledge base names: {knowledge_names}, File names: {file_names}, {knowledge_file_names}\n\nDo I need this resources to answer the question?"
                }
            ],
            response_model=KnowledgeUseDecision,
            model=Models.get_model_by_name_and_company(os.getenv("DEFAULT_AGENT_MODEL"), user.company_id)
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
                files.extend([{"type": "collection", "id": f"file-{file.id}"} for file in knowledge_files])

            if model_files:
                files.extend(model_files)

    # For code interpreter on OpenAI Responses API: skip RAG and text extraction entirely.
    # Files stay in metadata["files"] so litellm.py can upload them to OpenAI Files API.
    # For other providers (e.g. Gemini codeExecution), still extract file content as text
    # because those models don't support file uploads via the code interpreter path.
    code_interpreter_enabled = form_data.get("metadata", {}).get("code_interpreter_enabled", False)
    skip_file_processing = code_interpreter_enabled and _use_responses_api

    # First, decide if this is a RAG task or content extraction task
    if not skip_file_processing:
        try:
            has_user_collections = any(f.get("type") == "collection" for f in files)

            form_data, is_rag_task = await chat_file_intent_decision_handler(form_data,
                                                                             user) if not model_knowledge and not has_user_collections else (
                form_data, True)
        except Exception as e:
            log.exception(f"Error in file intent decision: {e}")
            is_rag_task = True  # Fallback to RAG
    else:
        is_rag_task = False  # Skipped: code interpreter on responses API handles files directly

    await check_disconnect(request)

    if not skip_file_processing and is_rag_task:
        # Proceed with normal RAG processing
        try:
            form_data, flags = await chat_completion_files_handler(request, form_data, user, extra_params)
            sources.extend(flags.get("sources", []))
        except Exception as e:
            log.exception(e)
    elif not skip_file_processing:
        # Handle non-RAG task: extract file content and append to user prompt
        try:
            file_contents = []

            for file_item in files:
                if isinstance(file_item, dict):
                    file_id = file_item.get("id")
                    if file_id:
                        # Skip image files and collections
                        if file_item.get("type") not in ["web_search_results", "collection"]:
                            try:
                                file_record = Files.get_file_by_id(file_id)
                                if file_record and file_record.meta:
                                    content_type = file_record.meta.get("content_type", "")
                                    # Skip image files
                                    if not content_type.startswith("image/"):
                                        content = extract_file_content_with_loader(file_id)
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

    # If context is not empty, insert it into the messages (only for RAG tasks)
    if len(sources) > 0 and is_rag_task:
        context_string = ""
        for source_idx, source in enumerate(sources):
            source_id = source.get("source", {}).get("name", "")

            if "document" in source:
                for doc_idx, doc_context in enumerate(source["document"]):
                    doc_metadata = source.get("metadata")
                    doc_source_id = None

                    if doc_metadata:
                        doc_source_id = doc_metadata[doc_idx].get("source", source_id)

                    if source_id:
                        context_string += f"<source><source_id>{doc_source_id if doc_source_id is not None else source_id}</source_id><source_context>{doc_context}</source_context></source>\n"
                    else:
                        # If there is no source_id, then do not include the source_id tag
                        context_string += f"<source><source_context>{doc_context}</source_context></source>\n"

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

        form_data["messages"] = add_or_update_system_message(
            rag_template(
                request.app.state.config.RAG_TEMPLATE, context_string, prompt
            ),
            form_data["messages"],
        )

    # If there are citations, add them to the data_items
    sources = [source for source in sources if source.get("source", {}).get("name", "")]

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
                        res = await generate_title(
                            request,
                            {
                                "model": message["model"],
                                "messages": messages,
                                "chat_id": metadata["chat_id"],
                            },
                            user,
                        )

                        if res and isinstance(res, dict):
                            title = res.get("title", "") or messages[0].get("content", "New chat")
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
        if event_emitter:
            if "selected_model_id" in response:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "selectedModelId": response["selected_model_id"],
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

                    # Send a webhook notification if the user is not active
                    if get_active_status_by_user_id(user.id) is None:
                        webhook_url = Users.get_user_webhook_url_by_id(user.id)
                        if webhook_url:
                            post_webhook(
                                webhook_url,
                                f"{title} - {request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}\n\n{content}",
                                {
                                    "action": "chat",
                                    "message": content,
                                    "title": title,
                                    "url": f"{request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}",
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
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {
                "model": model.id,
            },
        )

        # Handle as a background task
        async def post_response_handler(response, events):
            def serialize_content_blocks(content_blocks, raw=False):
                content = ""

                for block in content_blocks:
                    if block["type"] == "text":
                        content = f"{content}{block['content'].strip()}\n"
                    elif block["type"] == "tool_calls":
                        block_content = block.get("content", [])
                        results = block.get("results", [])

                        if results:

                            result_display_content = ""

                            for result in results:
                                tool_call_id = result.get("tool_call_id", "")
                                tool_name = ""

                                for tool_call in block_content:
                                    if tool_call.get("id", "") == tool_call_id:
                                        tool_name = tool_call.get("function", {}).get(
                                            "name", ""
                                        )
                                        break

                                result_display_content = f"{result_display_content}\n> {tool_name}: {result.get('content', '')}"

                            if not raw:
                                content = f'{content}\n<details type="tool_calls" done="true" content="{html.escape(json.dumps(block_content))}" results="{html.escape(json.dumps(results))}">\n<summary>Tool Executed</summary>\n{result_display_content}\n</details>\n'
                        else:
                            tool_calls_display_content = ""

                            for tool_call in block_content:
                                tool_calls_display_content = f"{tool_calls_display_content}\n> Executing {tool_call.get('function', {}).get('name', '')}"

                            if not raw:
                                content = f'{content}\n<details type="tool_calls" done="false" content="{html.escape(json.dumps(block_content))}">\n<summary>Tool Executing...</summary>\n{tool_calls_display_content}\n</details>\n'

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

            tool_calls = []

            content = message.get("content", "") if message else ""
            content_blocks = [
                {
                    "type": "text",
                    "content": content,
                }
            ]
            response_images = []

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
                    "data": {"model": model.id},
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

                    response_tool_calls = []

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

                            if "citations" in data:
                                nonlocal sources
                                sources = list(map(
                                    lambda citationUrl: {
                                        "source": {"name": citationUrl},
                                        "document": [citationUrl],
                                        "metadata": [{"source": citationUrl}],
                                        "distances": [0],
                                    },
                                    data["citations"]
                                ))

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
                                    for delta_image in delta_images:
                                        image_base64 = delta_image['image_url']["url"]

                                        response_images.append({"type": "image", "url": image_base64})

                                delta_tool_calls = delta.get("tool_calls", None)

                                if delta_tool_calls:
                                    for delta_tool_call in delta_tool_calls:
                                        tool_call_index = delta_tool_call.get("index")

                                        if tool_call_index is not None:
                                            if (
                                                    len(response_tool_calls)
                                                    <= tool_call_index
                                            ):
                                                response_tool_calls.append(
                                                    delta_tool_call
                                                )
                                            else:
                                                delta_name = delta_tool_call.get(
                                                    "function", {}
                                                ).get("name")
                                                delta_arguments = delta_tool_call.get(
                                                    "function", {}
                                                ).get("arguments")

                                                if delta_name:
                                                    response_tool_calls[
                                                        tool_call_index
                                                    ]["function"]["name"] += delta_name

                                                if delta_arguments:
                                                    response_tool_calls[
                                                        tool_call_index
                                                    ]["function"][
                                                        "arguments"
                                                    ] += delta_arguments

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

                                delta_annotations = delta.get("annotations", [])
                                if delta_annotations:
                                    seen_urls = {
                                        s["document"][0]
                                        for s in (sources or [])
                                        if s.get("document")
                                    }
                                    for annotation in delta_annotations:
                                        if annotation.get("type") == "url_citation":
                                            url_citation = annotation.get("url_citation", {})
                                            url = url_citation.get("url", "")
                                            title = url_citation.get("title") or url
                                            if url and url not in seen_urls:
                                                seen_urls.add(url)
                                                if sources is None:
                                                    sources = []

                                                sources.append({
                                                    "source": {"name": title},
                                                    "document": [url],
                                                    "metadata": [{"source": url, "name": title}],
                                                    "distances": [0],
                                                })

                                # Handle Claude/Vertex AI web search results via provider_specific_fields
                                provider_specific_fields = delta.get("provider_specific_fields", {})
                                if provider_specific_fields:
                                    web_search_results = provider_specific_fields.get("web_search_results")
                                    if web_search_results:
                                        seen_urls = {
                                            s["document"][0]
                                            for s in (sources or [])
                                            if s.get("document")
                                        }
                                        for result_group in web_search_results:
                                            for result in result_group.get("content", []):
                                                if result.get("type") == "web_search_result":
                                                    url = result.get("url", "")
                                                    title = result.get("title") or url
                                                    if url and url not in seen_urls:
                                                        seen_urls.add(url)
                                                        if sources is None:
                                                            sources = []
                                                        sources.append({
                                                            "source": {"name": title},
                                                            "document": [url],
                                                            "metadata": [{"source": url, "name": title}],
                                                            "distances": [0],
                                                        })

                                value = delta.get("content")

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

                    if response_tool_calls:
                        # Filter out server-side native tool calls (e.g. Claude's built-in
                        # web_search executed by the LLM provider) that are not in our
                        # user-defined tools. These have already been handled server-side
                        # and should not be displayed as "Tool Executed" in the UI.
                        user_tools = metadata.get("tools", {})
                        client_tool_calls = [
                            tc for tc in response_tool_calls
                            if tc.get("function", {}).get("name", "") in user_tools
                        ]
                        if client_tool_calls:
                            tool_calls.append(client_tool_calls)

                    if response.background:
                        await response.background()

                await stream_body_handler(response)

                MAX_TOOL_CALL_RETRIES = 5
                tool_call_retries = 0

                while len(tool_calls) > 0 and tool_call_retries < MAX_TOOL_CALL_RETRIES:
                    tool_call_retries += 1

                    response_tool_calls = tool_calls.pop(0)

                    content_blocks.append(
                        {
                            "type": "tool_calls",
                            "content": response_tool_calls,
                        }
                    )

                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": {
                                "content": serialize_content_blocks(content_blocks),
                            },
                        }
                    )

                    tools = metadata.get("tools", {})

                    results = []
                    for tool_call in response_tool_calls:
                        log.debug(f"Tool call: {tool_call}")
                        tool_call_id = tool_call.get("id", "")
                        tool_name = tool_call.get("function", {}).get("name", "")

                        tool_function_params = {}
                        try:
                            # json.loads cannot be used because some models do not produce valid JSON
                            tool_function_params = ast.literal_eval(
                                tool_call.get("function", {}).get("arguments", "{}")
                            )
                        except Exception as e:
                            log.debug(e)

                        tool_result = None

                        if tool_name in tools:
                            tool = tools[tool_name]
                            spec = tool.get("spec", {})

                            try:
                                required_params = spec.get("parameters", {}).get(
                                    "required", []
                                )
                                tool_function = tool["callable"]
                                tool_function_params = {
                                    k: v
                                    for k, v in tool_function_params.items()
                                    if k in required_params
                                }
                                tool_result = await tool_function(
                                    **tool_function_params
                                )
                            except Exception as e:
                                tool_result = str(e)

                        results.append(
                            {
                                "tool_call_id": tool_call_id,
                                "content": tool_result,
                            }
                        )

                    content_blocks[-1]["results"] = results

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
                                "content": serialize_content_blocks(content_blocks),
                            },
                        }
                    )

                    try:
                        res = await generate_chat_completion({
                            "stream": True,
                            "messages": [
                                *form_data["messages"],
                                {
                                    "role": "assistant",
                                    "content": serialize_content_blocks(
                                        content_blocks, raw=True
                                    ),
                                    "tool_calls": response_tool_calls,
                                },
                                *[
                                    {
                                        "role": "tool",
                                        "tool_call_id": result["tool_call_id"],
                                        "content": result["content"],
                                    }
                                    for result in results
                                ],
                            ],
                        }, user, model)

                        if isinstance(res, StreamingResponse):
                            await stream_body_handler(res)
                        else:
                            break
                    except Exception as e:
                        log.debug(e)
                        break
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

                # Send a webhook notification if the user is not active
                if get_active_status_by_user_id(user.id) is None:
                    webhook_url = Users.get_user_webhook_url_by_id(user.id)
                    if webhook_url:
                        post_webhook(
                            webhook_url,
                            f"{title} - {request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}\n\n{content}",
                            {
                                "action": "chat",
                                "message": content,
                                "title": title,
                                "url": f"{request.app.state.config.WEBUI_URL}/c/{metadata['chat_id']}",
                            },
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

            if response.background is not None:
                await response.background()

        # background_tasks.add_task(post_response_handler, response, events)
        task_id, _ = create_task(post_response_handler(response, events))
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

