"""Image generation/editing helpers for the GPT Image 2 model.

Pure, stateless transforms plus the gpt-image-2 API call, shared by the LiteLLM
router (payload construction) and the chat-response middleware (the tool reinvoke
loop). Living here keeps both layers from importing business logic out of each
other's modules.

The actual image bytes for editing are always inline base64 data URIs in the
conversation (see the vision-input flow), so no network fetch is needed to read
them — only a decode.
"""

import base64
import logging
import os

import aiohttp

from open_webui.env import AIOHTTP_CLIENT_TIMEOUT, SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OPENAI"])


# Dedicated aiohttp session for the (low-volume) image API calls. Kept separate
# from the router's session so this module has no dependency on the router.
_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            read_bufsize=10 * 1024 * 1024,  # 10 MB
        )
    return _session


def build_image_tool() -> dict:
    """Chat Completions function-tool definition for GPT Image 2
    """
    return {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": (
                "Generate or edit an image. Every image already in the conversation "
                "is tagged with a `[Image N]` marker (N is a 0-based index) in the text "
                "immediately before it. To edit one or more of those images, pass their "
                "N values in `input_image_indices` (e.g. [2] to edit the image tagged "
                "[Image 2]). Leave the list empty to generate a brand-new image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Description of the image to generate or the edit to apply.",
                    },
                    "size": {
                        "type": "string",
                        "enum": ["1024x1024", "1024x1536", "1536x1024"],
                        "default": "1024x1024",
                    },
                    "input_image_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "default": [],
                        "description": "The N values of the `[Image N]` markers to edit. Empty = generate a new image.",
                    },
                },
                "required": ["prompt"],
            },
        },
    }


def decode_data_uri(image_url: str):
    """Decode an inline `data:` image URI → (bytes, content_type)."""
    header, _, b64data = image_url.partition(",")
    content_type = header[len("data:"):].split(";")[0] or "image/png"
    return base64.b64decode(b64data), content_type


def label_images_for_model(messages):
    """Return a copy of `messages` where every image_url block is preceded by a
    visible `[Image N]` text marker.
    """
    labelled = []
    counter = 0
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            labelled.append(msg)
            continue
        new_content = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "image_url":
                new_content.append({"type": "text", "text": f"[Image {counter}]"})
                counter += 1
            new_content.append(block)
        labelled.append({**msg, "content": new_content})
    return labelled


def resolve_image_urls(indices, messages):
    """Map 0-based indices to the ordered image_url list in the conversation
    (user uploads + carried assistant images). Mirrors the ordering used by
    `label_images_for_model`, so index N here is the image tagged `[Image N]`."""
    if not indices:
        return []
    urls = []
    for msg in messages:
        msg_content = msg.get("content")
        if isinstance(msg_content, list):
            for block in msg_content:
                if block.get("type") == "image_url":
                    urls.append(block["image_url"]["url"])
    return [urls[i] for i in indices if 0 <= i < len(urls)]


async def generate_image(prompt: str, size: str, input_image_urls):
    """Generate or edit an image via the LiteLLM proxy (model `gpt-image-2`).
    """
    s = await _get_session()
    auth = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
    base_url = os.getenv("OPENAI_API_BASE_URL")
    try:
        if input_image_urls:
            form = aiohttp.FormData()
            form.add_field("model", "gpt-image-2")
            form.add_field("prompt", prompt)
            form.add_field("size", size)
            form.add_field("n", "1")
            for i, image_url in enumerate(input_image_urls):
                img_bytes, content_type = decode_data_uri(image_url)
                ext = (content_type.split("/")[-1] or "png")
                form.add_field(
                    "image[]",
                    img_bytes,
                    filename=f"image_{i}.{ext}",
                    content_type=content_type,
                )
            request_ctx = s.post(f"{base_url}/images/edits", data=form, headers=auth)
        else:
            body = {"model": "gpt-image-2", "prompt": prompt, "size": size, "n": 1}
            request_ctx = s.post(
                f"{base_url}/images/generations",
                json=body,
                headers={**auth, "Content-Type": "application/json"},
            )

        async with request_ctx as r:
            status = r.status
            try:
                result = await r.json()
            except Exception:
                result = {"error": {"message": (await r.text())[:500]}}

        if isinstance(result, dict) and result.get("error"):
            err = result["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            log.warning(f"gpt-image-2 rejected (HTTP {status}): {msg}")
            return None, f"image generation failed: {msg}"

        b64 = (result.get("data") or [{}])[0].get("b64_json")
        if not b64:
            log.warning(f"gpt-image-2 returned no image (HTTP {status}): {result}")
            return None, f"image API returned no image (HTTP {status})"
        return f"data:image/png;base64,{b64}", None
    except Exception as e:
        log.error(f"gpt-image-2 call failed: {e}")
        return None, f"image API call failed: {type(e).__name__}"
