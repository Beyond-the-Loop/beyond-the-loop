import base64
import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional

import requests


from fastapi import Depends, HTTPException, Request, APIRouter
from openai import OpenAI
from pydantic import BaseModel

from beyond_the_loop.config import CACHE_DIR
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS

from open_webui.utils.auth import get_verified_user
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["IMAGES"])

IMAGE_CACHE_DIR = Path(CACHE_DIR).joinpath("./image/generations/")
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


router = APIRouter()


class GenerateImageForm(BaseModel):
    prompt: str
    input_image_path: Optional[str] = None


def save_b64_image(b64_str):
    try:
        image_id = str(uuid.uuid4())

        if "," in b64_str:
            header, encoded = b64_str.split(",", 1)
            mime_type = header.split(";")[0]

            img_data = base64.b64decode(encoded)
            image_format = mimetypes.guess_extension(mime_type)

            image_filename = f"{image_id}{image_format}"
            file_path = IMAGE_CACHE_DIR / f"{image_filename}"
            with open(file_path, "wb") as f:
                f.write(img_data)
            return image_filename
        else:
            image_filename = f"{image_id}.png"
            file_path = IMAGE_CACHE_DIR.joinpath(image_filename)

            img_data = base64.b64decode(b64_str)

            # Write the image data to a file
            with open(file_path, "wb") as f:
                f.write(img_data)
            return image_filename

    except Exception as e:
        log.exception(f"Error saving image: {e}")
        return None


def save_url_image(url, headers=None):
    image_id = str(uuid.uuid4())
    try:
        if headers:
            r = requests.get(url, headers=headers)
        else:
            r = requests.get(url)

        r.raise_for_status()
        if r.headers["content-type"].split("/")[0] == "image":
            mime_type = r.headers["content-type"]
            image_format = mimetypes.guess_extension(mime_type)

            if not image_format:
                raise ValueError("Could not determine image type from MIME type")

            image_filename = f"{image_id}{image_format}"

            file_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}")
            with open(file_path, "wb") as image_file:
                for chunk in r.iter_content(chunk_size=8192):
                    image_file.write(chunk)
            return image_filename
        else:
            log.error("Url does not point to an image.")
            return None

    except Exception as e:
        log.exception(f"Error saving image: {e}")
        return None


async def image_generations(
    form_data: GenerateImageForm,
    user=Depends(get_verified_user),
):
    try:
        subscription = payments_service.get_subscription(user.company_id)

        if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
            await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

        client = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY")
        )

        print(form_data.input_image_path)

        if form_data.input_image_path:
            with open(form_data.input_image_path, "rb") as image_file:
                response = client.images.edit(
                    model="Nano Banana",
                    prompt=form_data.prompt,
                    image=image_file,
                )
        else:
            response = client.images.generate(
                model="Nano Banana",
                prompt=form_data.prompt,
            )

        image_base64 = response.data[0].b64_json

        image_bytes = base64.b64decode(image_base64)

        image_filename = f"{uuid.uuid4()}.png"
        image_path = IMAGE_CACHE_DIR / image_filename

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
            # Subtract credits for image generation
            await credit_service.subtract_credits_by_user_for_image(user)

        return [{"url": f"/cache/image/generations/{image_filename}"}]
    except Exception:
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT)
