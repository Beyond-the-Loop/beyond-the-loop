"""Store chat images as file references and resolve those references back to
inline bytes when a model needs to read them.

Chat content stored in the DB should hold a lightweight `/api/v1/files/{id}/content`
reference instead of a multi-MB base64 data URI. But any model that has to *see*
an image (vision) or *edit* it needs the raw bytes, so the reference is hydrated
back into a `data:` URI at request-build time.

Kept separate from image_generation.py (intentionally free of DB/storage logic)
and from middleware/litellm (which import each other, so a shared helper here
avoids an import cycle).
"""

import base64
import io
import logging
import re
import uuid

from beyond_the_loop.config import GCS_IMAGE_BUCKET_NAME
from beyond_the_loop.models.files import Files, FileForm
from beyond_the_loop.storage.provider import Storage
from beyond_the_loop.utils.image_generation import decode_data_uri

log = logging.getLogger(__name__)

_FILE_REF_RE = re.compile(r"/files/([^/]+)/content")


def persist_image_data_uri(data_uri: str, user_id: str) -> str:
    """Decode a `data:` image URI, store it in the image bucket as a file
    record, and return a backend content-reference URL. Falls back to the inline
    data URI if persistence fails, so a storage hiccup never loses the image."""
    try:
        img_bytes, content_type = decode_data_uri(data_uri)
        ext = content_type.split("/")[-1] or "png"
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{ext}"
        _, file_path = Storage.upload_file(
            io.BytesIO(img_bytes), filename, bucket_name=GCS_IMAGE_BUCKET_NAME
        )
        Files.insert_new_file(
            user_id,
            FileForm(
                id=file_id,
                filename=filename,
                path=file_path,
                meta={
                    "name": filename,
                    "content_type": content_type,
                    "size": len(img_bytes),
                },
            ),
        )
        return f"/api/v1/files/{file_id}/content"
    except Exception as e:
        log.error(f"Failed to persist image, keeping inline: {e}")
        return data_uri


def hydrate_image_ref_url(url: str) -> str:
    """Resolve a backend image reference (/api/v1/files/{id}/content) back into
    an inline `data:` URI so a model can read the bytes. Inline data URIs and
    unrecognized URLs pass through unchanged."""
    if not isinstance(url, str) or url.startswith("data:"):
        return url
    match = _FILE_REF_RE.search(url)
    if not match:
        return url
    try:
        file = Files.get_file_by_id(match.group(1))
        if not file:
            return url
        local_path = Storage.get_file(file.path)
        with open(local_path, "rb") as f:
            raw = f.read()
        content_type = (file.meta or {}).get("content_type", "image/png")
        return f"data:{content_type};base64,{base64.b64encode(raw).decode()}"
    except Exception as e:
        log.error(f"Failed to hydrate image ref ({url}): {e}")
        return url


def hydrate_image_refs_in_messages(messages) -> None:
    """In-place: rewrite every image_url block whose url is a backend file
    reference into an inline `data:` URI, so vision models receive the bytes
    instead of an unfetchable reference."""
    if not isinstance(messages, list):
        return
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "image_url":
                image_url = block.get("image_url")
                if isinstance(image_url, dict) and "url" in image_url:
                    image_url["url"] = hydrate_image_ref_url(image_url["url"])
