import asyncio
import base64
import json
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

import requests


from fastapi import Depends, HTTPException, Request, APIRouter
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
    model: Optional[str] = None
    prompt: str
    size: Optional[str] = None
    n: int = 1
    negative_prompt: Optional[str] = None
    input_image_data: Optional[str] = None


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


@router.post("/generations")
async def image_generations(
    request: Request,
    form_data: GenerateImageForm,
    user=Depends(get_verified_user),
):
    width, height = tuple(map(int, request.app.state.config.IMAGE_SIZE.split("x")))

    try:
        subscription = payments_service.get_subscription(user.company_id)

        if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
            await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

        if request.app.state.config.IMAGE_GENERATION_ENGINE == "flux":
            # Black Forest Labs Flux Kontext Pro
            headers = {
                "Content-Type": "application/json",
                "x-key": request.app.state.config.BLACK_FOREST_LABS_API_KEY,
            }

            # Prepare the request data

            # Calculate aspect ratio from width and height
            def calculate_aspect_ratio(w, h):
                from math import gcd
                ratio_gcd = gcd(w, h)
                return f"{w // ratio_gcd}:{h // ratio_gcd}"

            data = {
                "prompt": form_data.prompt,
                "aspect_ratio": calculate_aspect_ratio(width, height),
                "output_format": "jpeg",
                "safety_tolerance": 2,
                "input_image": form_data.input_image_data,
            }

            # Add optional parameters if provided
            if form_data.negative_prompt:
                # Note: Flux Kontext Pro doesn't have explicit negative prompt support
                # We could potentially incorporate it into the main prompt
                data["prompt"] = f"{form_data.prompt}. Avoid: {form_data.negative_prompt}"

            # Make the initial request to start generation
            r = await asyncio.to_thread(
                requests.post,
                url="https://api.eu.bfl.ai/v1/flux-kontext-max",
                json=data,
                headers=headers,
            )

            r.raise_for_status()
            initial_response = r.json()
            
            task_id = initial_response["id"]
            polling_url = initial_response["polling_url"]
            
            log.debug(f"Flux task started with ID: {task_id}")

            # Poll for completion
            max_attempts = 120  # 2 minutes with 1-second intervals
            attempt = 0
            
            while attempt < max_attempts:
                await asyncio.sleep(1)  # Wait 1 second between polls
                
                # Poll the result
                poll_response = await asyncio.to_thread(
                    requests.get,
                    url=polling_url,
                    headers={"x-key": request.app.state.config.BLACK_FOREST_LABS_API_KEY},
                )
                
                poll_response.raise_for_status()
                result = poll_response.json()
                
                status = result.get("status")
                log.debug(f"Flux generation status: {status}")
                
                if status == "Ready":
                    # Generation completed successfully
                    image_url = result["result"]["sample"]
                    
                    # Download and save the image
                    image_filename = save_url_image(image_url)

                    # Save metadata
                    file_body_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}.json")
                    with open(file_body_path, "w") as f:
                        json.dump({**data, "task_id": task_id, "status": status}, f)

                    if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                        # Subtract credits for image generation
                        await credit_service.subtract_credits_by_user_for_image(user, "flux-kontext-max")

                    return [{"url": f"/cache/image/generations/{image_filename}"}]

                elif status in ["Error", "Failed"]:
                    error_msg = result.get("details", {}).get("error", "Generation failed")
                    raise HTTPException(status_code=400, detail=f"Flux generation failed: {error_msg}")
                
                attempt += 1
            
            # If we get here, the generation timed out
            raise HTTPException(status_code=408, detail="Flux generation timed out")
        else:
            raise HTTPException(status_code=400, detail="Unknown image generation engine")
    except Exception:
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT)
