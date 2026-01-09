import time
import logging
import sys
import os
import base64
import re
import mimetypes
import asyncio
from io import BytesIO

import httpx
import json
import html
import ast
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from fastapi import Request
from starlette.responses import StreamingResponse
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.users import Users
from beyond_the_loop.models.models import ModelModel
from beyond_the_loop.config import CODE_INTERPRETER_FILE_HINT_TEMPLATE
from beyond_the_loop.config import CODE_INTERPRETER_SUMMARY_PROMPT, CODE_INTERPRETER_FAIL_PROMPT
from beyond_the_loop.models.files import FileForm
from beyond_the_loop.socket.main import (
    get_event_call,
    get_event_emitter,
    get_active_status_by_user_id,
)
from open_webui.routers.tasks import (
    generate_queries,
    generate_title,
    generate_image_prompt,
    generate_chat_tags,
)
from open_webui.routers.retrieval import process_web_search, SearchForm
from open_webui.routers.images import image_generations, GenerateImageForm
from open_webui.utils.webhook import post_webhook
from beyond_the_loop.models.users import UserModel
from beyond_the_loop.models.models import Models
from beyond_the_loop.retrieval.utils import get_sources_from_files
from beyond_the_loop.routers.openai import generate_chat_completion
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
)
from open_webui.tasks import create_task
from beyond_the_loop.config import (
    CACHE_DIR,
    CODE_INTERPRETER_PROMPT,
    DEFAULT_AGENT_MODEL,
)
from open_webui.env import (
    SRC_LOG_LEVELS,
    GLOBAL_LOG_LEVEL,
    ENABLE_REALTIME_CHAT_SAVE,
)
from open_webui.constants import TASKS
from open_webui.routers.retrieval import process_file, ProcessFileForm
from beyond_the_loop.services.credit_service import credit_service

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

async def chat_web_search_handler(
    request: Request, form_data: dict, extra_params: dict, user
):
    event_emitter = extra_params["__event_emitter__"]

    web_search_files = []

    await event_emitter(
        {
            "type": "status",
            "data": {
                "action": "web_search",
                "description": "Generating search query",
                "done": False,
            },
        }
    )

    messages = form_data["messages"]
    user_message = get_last_user_message(messages)

    try:
        res = await generate_queries(
            request,
            {
                "model": form_data["model"],
                "messages": messages,
                "prompt": user_message,
                "type": "web_search",
            },
            user,
        )

        response = res["choices"][0]["message"]["content"]

        try:
            bracket_start = response.find("{")
            bracket_end = response.rfind("}") + 1

            if bracket_start == -1 or bracket_end == -1:
                raise Exception("No JSON object found in the response")

            response = response[bracket_start:bracket_end]
            queries = json.loads(response)
            queries = queries.get("queries", [])
        except Exception as e:
            log.exception(e)
            queries = [response]

    except Exception as e:
        log.exception(e)
        queries = [user_message]

    if len(queries) == 0:
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": "No search query generated",
                    "done": True,
                },
            }
        )
        return web_search_files

    search_query = queries[0]

    await event_emitter(
        {
            "type": "status",
            "data": {
                "action": "web_search",
                "description": 'Searching "{{searchQuery}}"',
                "query": search_query,
                "done": False,
            },
        }
    )

    try:

        # Offload process_web_search to a separate thread
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            results = await loop.run_in_executor(
                executor,
                lambda: process_web_search(
                    request,
                    SearchForm(
                        **{
                            "query": search_query,
                        }
                    ),
                    user,
                ),
            )

        if results:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "web_search",
                        "description": "Searched {{count}} sites",
                        "query": search_query,
                        "urls": results["filenames"],
                        "done": True,
                    },
                }
            )

            web_search_files.append(
                {
                    "collection_name": results["collection_name"],
                    "name": search_query,
                    "type": "web_search_results",
                    "urls": results["filenames"],
                }
            )
        else:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "action": "web_search",
                        "description": "No search results found",
                        "query": search_query,
                        "done": True,
                        "error": True,
                    },
                }
            )

        await credit_service.subtract_credits_by_user_for_web_search(user)
    except Exception as e:
        log.exception(e)
        await event_emitter(
            {
                "type": "status",
                "data": {
                    "action": "web_search",
                    "description": 'Error searching "{{searchQuery}}"',
                    "query": search_query,
                    "done": True,
                    "error": True,
                },
            }
        )

    return web_search_files


async def chat_image_generation_handler(
    request: Request, form_data: dict, extra_params: dict, user
):
    __event_emitter__ = extra_params["__event_emitter__"]
    await __event_emitter__(
        {
            "type": "status",
            "data": {"description": "Generating an image", "done": False},
        }
    )

    messages = form_data["messages"]
    user_message = get_last_user_message(messages)

    prompt = user_message

    already_generated_images = [
        re.search(r'/cache/image/generations/[^)\s]+', x["content"]).group(0)
        for x in messages
        if x["role"] == "assistant" and "/cache/image/generations/" in x["content"]
    ]

    edit_last_image = False

    if len(already_generated_images) > 0:
        model = Models.get_model_by_name_and_company(DEFAULT_AGENT_MODEL.value, user.company_id)

        decision_messages = messages.copy()
        decision_messages.append({
            "role": "user",
            "content": "Please decide if the user wants to edit the last image generated. IMPORTANT: Only respond with 'yes' or 'no' and nothing else."
        })

        decision_form_data = {
            "model": model.id,
            "messages": decision_messages,
            "stream": False,
            "metadata": {
                "chat_id": None,
                "agent_or_task_prompt": True
            },
            "temperature": 0.0
        }

        response = await generate_chat_completion(decision_form_data, user)

        response_message = response.get('choices', [{}])[0].get('message', {}).get('content', '')

        edit_last_image = response_message.lower().strip() == 'yes'

    if not edit_last_image and request.app.state.config.ENABLE_IMAGE_PROMPT_GENERATION:
        try:
            res = await generate_image_prompt(
                request,
                {
                    "model": form_data["model"],
                    "messages": messages,
                },
                user,
            )

            response = res["choices"][0]["message"]["content"]

            try:
                bracket_start = response.find("{")
                bracket_end = response.rfind("}") + 1

                if bracket_start == -1 or bracket_end == -1:
                    raise Exception("No JSON object found in the response")

                response = response[bracket_start:bracket_end]
                response = json.loads(response)
                prompt = response.get("prompt", [])
            except Exception as e:
                prompt = user_message

        except Exception as e:
            log.exception(e)
            prompt = user_message

    input_image_data = None

    if edit_last_image:
        try:
            last_image_path = already_generated_images[-1]
            full_image_path = os.path.normpath(os.path.join(CACHE_DIR, last_image_path.lstrip('/cache/')))
            if not full_image_path.startswith(CACHE_DIR):
                raise Exception("Access to the specified path is not allowed.")
            with open(full_image_path, 'rb') as image_file:
                image_data = image_file.read()
                mime_type = mimetypes.guess_type(full_image_path)[0] or 'image/jpeg'
                base64_data = base64.b64encode(image_data).decode('utf-8')
                input_image_data = f"data:{mime_type};base64,{base64_data}"
        except Exception:
            pass # input_image_data will remain None

    try:
        images = await image_generations(
            request=request,
            form_data=GenerateImageForm(**{"prompt": prompt, "input_image_data": input_image_data}),
            user=user,
        )

        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Generated an image", "done": True},
            }
        )

        for image in images:
            await __event_emitter__(
                {
                    "type": "message",
                    "data": {"content": f"![Generated Image]({image['url']})\n"},
                }
            )

        system_message_content = "<context>An image has been generated and displayed above. Do not generate any image markdown. Acknowledge that the image has been generated and tell the user in his language,that you can edit the image if he asks you to do so.</context>"

    except Exception as e:
        log.exception(e)
        await __event_emitter__(
            {
                "type": "status",
                "data": {
                    "description": f"An error occured while generating an image",
                    "done": True,
                },
            }
        )

        system_message_content = "<context>Unable to generate an image, tell the user that an error occured</context>"

    if system_message_content:
        form_data["messages"] = add_or_update_system_message(
            system_message_content, form_data["messages"]
        )

    return form_data


async def chat_file_intent_decision_handler(
        body: dict, user: UserModel
) -> tuple[dict, bool]:
    """
    Decide if the user's intent is RAG (search/query) or translation/content extraction.
    Returns (modified_body, is_rag_task)
    """

    files = body.get("metadata", {}).get("files", [])

    if not files:
        return body, True  # No files, proceed normally

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
        return body, True  # No non-image files, proceed with normal RAG
    
    # Use DEFAULT_AGENT_MODEL to decide intent
    user_message = get_last_user_message(body["messages"])
    if not user_message:
        return body, True  # No user message, proceed with RAG
    
    try:
        model = Models.get_model_by_name_and_company(DEFAULT_AGENT_MODEL.value, user.company_id)
        if not model:
            log.warning(f"DEFAULT_AGENT_MODEL {DEFAULT_AGENT_MODEL.value} not found for company {user.company_id}")
            return body, True  # Fallback to RAG
        
        # Create decision prompt
        decision_messages = [
            {
                "role": "system",
                "content": "You are an AI assistant that determines user intent. The user has attached non-image files to their message. Analyze their message and determine:\n\nFor the user's intent, is it necessary to use the ENTIRE content of the document?\n\nExamples that need ENTIRE content:\n- Translation tasks\n- Summarization of the whole document\n- Editing/proofreading the entire document\n- Content analysis requiring full context\n- Format conversion\n- Complete document review\n\nExamples that can use RAG (partial content):\n- Answering specific questions about the document\n- Finding particular information or facts\n- Searching for specific topics or sections\n- Comparing specific parts\n\nRespond with ONLY 'FULL' or 'RAG' - nothing else."
            },
            {
                "role": "user",
                "content": f"User message: {user_message}\n\nFile names: {', '.join([f.get('name', 'unknown') for f in non_image_files])}\n\nWhat is the user's intent?"
            }
        ]
        
        decision_form_data = {
            "model": model.id,
            "messages": decision_messages,
            "stream": False,
            "metadata": {
                "chat_id": None,
                "agent_or_task_prompt": True
            },
            "temperature": 0.0
        }
        
        response = await generate_chat_completion(decision_form_data, user)
        response_content = response.get('choices', [{}])[0].get('message', {}).get('content', '').strip().upper()
        
        is_rag_task = response_content == 'RAG'
        log.debug(f"File intent decision: {response_content} -> is_rag_task: {is_rag_task}")

        return body, is_rag_task
        
    except Exception as e:
        log.exception(f"Error in file intent decision: {e}")
        return body, True  # Fallback to RAG on error


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
    request: Request, body: dict, user: UserModel
) -> tuple[dict, dict[str, list]]:
    sources = []

    if files := body.get("metadata", {}).get("files", None):
        try:
            queries_response = await generate_queries(
                request,
                {
                    "model": body["model"],
                    "messages": body["messages"],
                    "type": "retrieval",
                },
                user,
            )
            queries_response = queries_response["choices"][0]["message"]["content"]

            try:
                bracket_start = queries_response.find("{")
                bracket_end = queries_response.rfind("}") + 1

                if bracket_start == -1 or bracket_end == -1:
                    raise Exception("No JSON object found in the response")

                queries_response = queries_response[bracket_start:bracket_end]
                queries_response = json.loads(queries_response)
            except Exception as e:
                queries_response = {"queries": [queries_response]}

            queries = queries_response.get("queries", [])
        except Exception as e:
            queries = []

        if len(queries) == 0:
            queries = [get_last_user_message(body["messages"])]

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

        log.debug(f"rag_contexts:sources: {sources}")

    return body, {"sources": sources}


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


async def process_chat_payload(request, form_data, metadata, user, model: ModelModel):
    form_data = apply_params_to_form_data(form_data)

    # Remove variables and tool_ids from form_data. They're legacy
    form_data.pop("variables", None)
    form_data.pop("tool_ids", None)

    log.debug(f"form_data: {form_data}")


    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

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

    features = form_data.pop("features", None)

    user_message = get_last_user_message(form_data["messages"])

    model_knowledge = model.meta.knowledge
    model_files = model.meta.files

    # Remove file duplicates and remove files from form_data, add it to metadata
    files = form_data.pop("files", [])
    files = list({json.dumps(f, sort_keys=True): f for f in files}.values())

    metadata = {
        **metadata,
        "files": files,
    }

    form_data["metadata"] = metadata

    if model_knowledge or model_files:
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
        knowledge_files = []
        for item in model_knowledge:
            if item.get("collection_name"):
                knowledge_files.append(
                    {
                        "id": item.get("collection_name"),
                        "name": item.get("name"),
                        "legacy": True,
                    }
                )
            elif item.get("collection_names"):
                knowledge_files.append(
                    {
                        "name": item.get("name"),
                        "type": "collection",
                        "collection_names": item.get("collection_names"),
                        "legacy": True,
                    }
                )
            else:
                knowledge_files.extend([{"type": "collection", "id": f"file-{file_id}"} for file_id in item["data"]["file_ids"]])

        files.extend(knowledge_files)

    if model_files:
        files.extend(model_files)

    # First, decide if this is a RAG task or content extraction task
    try:
        form_data, is_rag_task = await chat_file_intent_decision_handler(form_data, user) if not model_knowledge else (form_data, True)

    except Exception as e:
        log.exception(f"Error in file intent decision: {e}")
        is_rag_task = True  # Fallback to RAG

    if is_rag_task:
        # Proceed with normal RAG processing
        try:
            form_data, flags = await chat_completion_files_handler(request, form_data, user)
            sources.extend(flags.get("sources", []))
        except Exception as e:
            log.exception(e)
    else:
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
                                        file_contents.append(f"\n\n--- Content of {file_record.filename} ---\n{content}\n--- End of {file_record.filename} ---")
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


        if not ("code_interpreter" in features and features["code_interpreter"]):
            form_data["messages"] = add_or_update_system_message(
                rag_template(
                    request.app.state.config.RAG_TEMPLATE, context_string, prompt
                ),
                form_data["messages"],
            )
        else:
            form_data["messages"] = add_or_update_system_message(
                context_string,
                form_data["messages"]
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

    if features:
        if "web_search" in features and features["web_search"]:
            web_search_files = await chat_web_search_handler(
                request, form_data, extra_params, user
            )

            files.extend(web_search_files)

        if "image_generation" in features and features["image_generation"]:
            form_data = await chat_image_generation_handler(
                request, form_data, extra_params, user
            )

        if "code_interpreter" in features and features["code_interpreter"]:
            form_data["messages"] = add_or_update_system_message(
                CODE_INTERPRETER_PROMPT, form_data["messages"]
            )

            model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_CODE_INTERPRETER_MODEL"), user.company_id)
            form_data["model"] = model.id

            form_data["metadata"]["images"] = []

            for message in form_data["messages"]:
                if "content" in message and isinstance(message["content"], list):
                    for c in message["content"]:
                        if c.get("type") == "image_url":
                            url = c.get("image_url", {}).get("url")

                            if url:
                                ext = get_extension_from_base64(url)
                                filename = f"uploaded_image{len(form_data['metadata']['images']) + 1}.{ext}" if ext else "uploaded_image.bin"

                                parts = url.split(',')
                                if len(parts) > 1:
                                    url = parts[1]
                                else:
                                    url = parts[0]

                                form_data["metadata"]["images"].append({
                                    "name": filename,
                                    "content": url
                                })

            code_interpreter_files = Chats.get_chat_by_id(metadata["chat_id"]).chat.get("code_interpreter_files", [])
            form_data["metadata"]["code_interpreter_files"] = code_interpreter_files

            non_knowledge_files = [f for f in files if f.get("file") and "filename" in f["file"]]

            # Inform the LLM about available uploaded files so it can reference them in generated code
            if code_interpreter_files or non_knowledge_files or form_data["metadata"]["images"]:
                # Build a concise instruction listing accessible filenames (non-image, non-collection)
                file_list_str = ", ".join(f["file"]["filename"] for f in non_knowledge_files) + ", ".join(
                    image["name"] for image in form_data["metadata"]["images"]) + ", ".join(
                    file["name"] for file in code_interpreter_files)

                code_interpreter_file_hint_template = CODE_INTERPRETER_FILE_HINT_TEMPLATE
                form_data["messages"] = add_or_update_user_message(
                    code_interpreter_file_hint_template.replace("{{file_list}}", file_list_str), form_data["messages"])

    return form_data, metadata, events


async def process_chat_response(
    request, response, form_data, user, events, metadata, tasks
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
                            if len(res.get("choices", [])) == 1:
                                title_string = (
                                    res.get("choices", [])[0]
                                    .get("message", {})
                                    .get("content", message.get("content", "New chat"))
                                )
                            else:
                                title_string = ""

                            title_string = title_string[
                                title_string.find("{") : title_string.rfind("}") + 1
                            ]

                            try:
                                title = json.loads(title_string).get(
                                    "title", "New chat"
                                )
                            except Exception as e:
                                title = ""

                            if not title:
                                title = messages[0].get("content", "New chat")

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

                if TASKS.TAGS_GENERATION in tasks and tasks[TASKS.TAGS_GENERATION]:
                    res = await generate_chat_tags(
                        request,
                        {
                            "model": message["model"],
                            "messages": messages,
                            "chat_id": metadata["chat_id"],
                        },
                        user,
                    )

                    if res and isinstance(res, dict):
                        if len(res.get("choices", [])) == 1:
                            tags_string = (
                                res.get("choices", [])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                        else:
                            tags_string = ""

                        tags_string = tags_string[
                            tags_string.find("{") : tags_string.rfind("}") + 1
                        ]

                        try:
                            tags = json.loads(tags_string).get("tags", [])
                            Chats.update_chat_tags_by_id(
                                metadata["chat_id"], tags, user
                            )

                            await event_emitter(
                                {
                                    "type": "chat:tags",
                                    "data": tags,
                                }
                            )
                        except Exception as e:
                            pass

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
        model_id = form_data.get("model", "")

        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {
                "model": model_id,
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

                    elif block["type"] == "code_interpreter":
                        attributes = block.get("attributes", {})
                        output = block.get("output", None)
                        lang = attributes.get("lang", "")

                        if output:
                            output = html.escape(json.dumps(output))

                            # RAW means without code interpreter activated - not code execution
                            if raw:
                                content = f'{content}\n<code_interpreter type="code" lang="{lang}">\n{block["content"]}\n</code_interpreter>\n```output\n{output}\n```\n'
                            else:
                                content = f'{content}\n<details type="code_interpreter" done="true" output="{output}">\n<summary>Analyzed</summary>\n```{lang}\n{block["content"]}\n```\n</details>\n'
                        else:
                            if raw:
                                content = f'{content}\n<code_interpreter type="code" lang="{lang}">\n{block["content"]}\n</code_interpreter>\n'
                            else:
                                content = f'{content}\n<details type="code_interpreter" done="false">\n<summary>Analyzing...</summary>\n```{lang}\n{block["content"]}\n```\n</details>\n'

                    else:
                        block_content = str(block["content"]).strip()
                        content = f"{content}{block['type']}: {block_content}\n"

                return content.strip()

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
                                match.end() :
                            ]  # Content after opening tag

                            # Remove the start tag from the currently handling text block
                            content_blocks[-1]["content"] = content_blocks[-1][
                                "content"
                            ].replace(match.group(0), "")

                            if before_tag:
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

            sources = None  # Store sources from the LLMs ("citations") at this scope

            # We might want to disable this by default
            detect_reasoning = True
            detect_code_interpreter = metadata.get("features", {}).get(
                "code_interpreter", False
            )

            reasoning_tags = [
                "think",
                "thinking",
                "reason",
                "reasoning",
                "thought",
                "Thought",
            ]

            code_interpreter_tags = ["code_interpreter"]

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

                    response_tool_calls = []

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
                        data = data[len("data:") :].strip()

                        try:
                            data = json.loads(data)

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

                                value = delta.get("content")

                                if value:
                                    content = f"{content}{value}"

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

                                    if detect_code_interpreter:
                                        content, content_blocks, end = (
                                            tag_content_handler(
                                                "code_interpreter",
                                                code_interpreter_tags,
                                                content,
                                                content_blocks,
                                            )
                                        )

                                        if end:
                                            break

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
                                    else:
                                        data = {
                                            "content": serialize_content_blocks(
                                                content_blocks
                                            ),
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
                        tool_calls.append(response_tool_calls)

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
                        print("\n\n" + str(tool_call) + "\n\n")
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
                            "model": model_id,
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
                        }, user)

                        if isinstance(res, StreamingResponse):
                            await stream_body_handler(res)
                        else:
                            break
                    except Exception as e:
                        log.debug(e)
                        break

                if detect_code_interpreter:
                    max_retries = 3
                    retries = 0

                    while (
                        content_blocks[-1]["type"] == "code_interpreter"
                        and retries < max_retries
                    ):
                        retries += 1
                        log.debug(f"Attempt count: {retries}")

                        output = ""

                        try:
                            if content_blocks[-1]["attributes"].get("type") == "code":
                                # Execute code via external Python executor service instead of frontend event
                                try:
                                    executor_url = os.getenv("PYTHON_EXECUTOR_URL")

                                    if not executor_url:
                                        raise RuntimeError("PYTHON_EXECUTOR_URL environment variable is not set")

                                    code_to_run = content_blocks[-1]["content"]

                                    code_execution_id = str(uuid4())

                                    await event_emitter(
                                        {
                                            "type": "source",
                                            "data": {
                                                "type": "code_execution",
                                                "id": code_execution_id,
                                                "name": "Python Execution",
                                                "language": "Python",
                                                "code": code_to_run,
                                            },
                                        }
                                    )

                                    # Prepare attached files for the Python executor: we embed small files as base64
                                    files_to_send = []

                                    try:
                                        attached_files = (metadata or {}).get("files", []) + (metadata or {}).get("code_interpreter_files", [])

                                        for file_item in attached_files or []:
                                            if not isinstance(file_item, dict):
                                                continue
                                            file_id = file_item.get("id")

                                            if not file_id:
                                                continue
                                            # Skip collections and web_search results
                                            if file_item.get("type") in ["collection", "web_search_results"]:
                                                continue
                                            try:
                                                file_record = Files.get_file_by_id(file_id)
                                                if not file_record or not file_record.meta:
                                                    continue

                                                # Fetch local path and read bytes
                                                try:
                                                    local_path = Storage.get_file(file_record.path)
                                                    with open(local_path, "rb") as f:
                                                        raw = f.read()

                                                    b64 = base64.b64encode(raw).decode("ascii")
                                                    name = file_record.meta.get("name", file_record.filename) if file_record.meta else file_record.filename
                                                    files_to_send.append({
                                                        "name": name,
                                                        "content": b64
                                                    })
                                                except Exception as file_err:
                                                    print(f"Failed to stage file {file_id} for executor: {file_err}")
                                                    continue
                                            except Exception as file_meta_err:
                                                print(f"Error accessing file metadata {file_id}: {file_meta_err}")
                                                continue

                                    except Exception as prep_err:
                                        print(f"Error preparing files for python executor: {prep_err}")

                                    async with httpx.AsyncClient(timeout=60) as client:
                                        payload = {"code": code_to_run}
                                        if files_to_send:
                                            payload["files"] = files_to_send

                                        images = (metadata or {}).get("images", [])

                                        if (metadata or {}).get("images", []):
                                            payload["files"] = payload.get("files", []) + images

                                        resp = await client.post(executor_url, json=payload)
                                        resp.raise_for_status()
                                        data = resp.json()

                                    # Expecting structure:
                                    # {
                                    #   "success": true,
                                    #   "stdout": "...",
                                    #   "stderr": "...",
                                    #   "files": [{name: "", url: "", binary: ""}, ...],
                                    #   "execution_id": "..."
                                    # }

                                    if isinstance(data, dict):
                                        await credit_service.subtract_credits_by_user_for_code_interpreter(user)

                                        output = data
                                        # Ensure keys exist
                                        output.setdefault("success", False)
                                        output.setdefault("stdout", "")
                                        output.setdefault("stderr", "")
                                        output.setdefault("files", [])
                                        output.setdefault("execution_id", "")

                                        # Process returned files (non-images)
                                        if output.get("files"):
                                            for file_item in output["files"]:
                                                if not isinstance(file_item, dict):
                                                    continue
                                                file_name = file_item.get("name")
                                                file_bytes = file_item.get("bytes")

                                                if not file_bytes:
                                                    continue

                                                try:
                                                    contents, file_path = Storage.upload_file(BytesIO(base64.b64decode(file_bytes)), file_name)

                                                    new_file_id = str(uuid4())

                                                    content_type, _ = mimetypes.guess_type(file_name)

                                                    Files.insert_new_file(
                                                        user.id,
                                                        FileForm(
                                                            **{
                                                                "id": new_file_id,
                                                                "filename": file_name,
                                                                "path": file_path,
                                                                "meta": {
                                                                    "name": file_name,
                                                                    "size": len(contents),
                                                                    "content_type": content_type
                                                                },
                                                            }
                                                        ),
                                                    )

                                                    process_file(request, ProcessFileForm(file_id=new_file_id), user=user)

                                                    file_item = Files.get_file_by_id(id=new_file_id)

                                                    chat_file_item = {
                                                        "type": "file",
                                                        "file": file_item.model_dump(),
                                                        "id": new_file_id,
                                                        "url": None,
                                                        "name": file_item.filename,
                                                        "collection_name": file_item.meta.get("collection_name"),
                                                        "size": file_item.meta.get("size"),
                                                        "itemId": new_file_id
                                                    }

                                                    chat = Chats.get_chat_by_id(metadata["chat_id"])
                                                    chat.chat["code_interpreter_files"] = chat.chat.get("code_interpreter_files", []) + [chat_file_item]
                                                    Chats.update_chat_by_id(metadata.get("chat_id"), chat.chat)
                                                except Exception as file_upload_err:
                                                    print("Error on created file processing", file_upload_err)
                                    else:
                                        output = str(data)
                                except Exception as exec_err:
                                    output = str(exec_err)
                        except Exception as e:
                            output = str(e)

                        content_blocks[-1]["output"] = output

                        # Emit the final code execution result event with the same id
                        block = content_blocks[-1]

                        await event_emitter(
                            {
                                "type": "source",
                                "data": {
                                    "type": "code_execution",
                                    "id": code_execution_id,
                                    "name": "Python Execution",
                                    "language": "Python",
                                    "code": block.get("content", ""),
                                    "result": {
                                        **({"output": output.get("stdout") if isinstance(output, dict) else ""}),
                                        **({"error": output.get("stderr") if isinstance(output, dict) else output}),
                                        **({"files": output.get("files") if isinstance(output, dict) else []}),
                                    },
                                },
                            }
                        )

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

                        # After code execution completes, call the LLM again to summarize the result
                        try:
                            # Build follow-up messages
                            followup_messages = [
                                *form_data["messages"],
                                {
                                    "role": "assistant",
                                    "content": serialize_content_blocks(content_blocks, raw=True),
                                },
                                {
                                    "role": "user",
                                    "content": json.dumps({
                                        "instruction": CODE_INTERPRETER_SUMMARY_PROMPT
                                    }),
                                }
                            ] if retries < max_retries else [
                                *form_data["messages"],
                                {
                                    "role": "assistant",
                                    "content": serialize_content_blocks(content_blocks, raw=True),
                                },
                                {
                                    "role": "user",
                                    "content": json.dumps({
                                        "instruction": CODE_INTERPRETER_FAIL_PROMPT
                                    }),
                                }
                            ]

                            res = await generate_chat_completion({
                                "model": Models.get_model_by_name_and_company(
                                    os.getenv("DEFAULT_CODE_INTERPRETER_MODEL"), user.company_id).id,
                                "stream": True,
                                "messages": followup_messages,
                                "metadata": {
                                    "agent_or_task_prompt": True
                                }
                            }, user)

                            if isinstance(res, StreamingResponse):
                                await stream_body_handler(res)


                        except Exception as follow_err:
                            print(f"Follow-up LLM generation failed: {follow_err}")

                title = Chats.get_chat_title_by_id(metadata["chat_id"])

                data = {
                    "done": True,
                    "content": serialize_content_blocks(content_blocks),
                    "title": title,
                }

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
                print("Task was cancelled!")
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

def get_extension_from_base64(b64_string):
    match = re.match(r"data:(image/[^;]+);base64,", b64_string)
    if not match:
        return None  # Not a valid base64 image with MIME info

    mime_type = match.group(1)  # e.g. "image/png"

    # Map MIME → file extension
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/svg+xml": "svg",
    }

    return mapping.get(mime_type, None)
