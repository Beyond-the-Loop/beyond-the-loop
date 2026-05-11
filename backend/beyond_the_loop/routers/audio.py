import hashlib
import json
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path

import aiohttp
import aiofiles
import requests

from fastapi import (
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
    APIRouter,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel


from open_webui.utils.auth import get_admin_user, get_verified_user
from beyond_the_loop.config import (
    WHISPER_MODEL_AUTO_UPDATE,
    WHISPER_MODEL_DIR,
    CACHE_DIR,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    SRC_LOG_LEVELS,
    DEVICE_TYPE,
)
from beyond_the_loop.services.credit_service import credit_service
from beyond_the_loop.services.payments_service import payments_service

router = APIRouter()

# Constants
MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["AUDIO"])

SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


##########################################
#
# Utility functions
#
##########################################

from pydub import AudioSegment
from pydub.utils import mediainfo


def is_mp4_audio(file_path):
    """Check if the given file is an MP4 audio file."""
    if not os.path.isfile(file_path):
        log.warning(f"File not found: {file_path}")
        return False

    info = mediainfo(file_path)
    if (
        info.get("codec_name") == "aac"
        and info.get("codec_type") == "audio"
        and info.get("codec_tag_string") == "mp4a"
    ):
        return True
    return False


def convert_mp4_to_wav(file_path, output_path):
    """Convert MP4 audio file to WAV format."""
    audio = AudioSegment.from_file(file_path, format="mp4")
    audio.export(output_path, format="wav")
    log.info(f"Converted {file_path} to {output_path}")


def set_faster_whisper_model(model: str, auto_update: bool = False):
    whisper_model = None
    if model:
        from faster_whisper import WhisperModel

        faster_whisper_kwargs = {
            "model_size_or_path": model,
            "device": DEVICE_TYPE if DEVICE_TYPE and DEVICE_TYPE == "cuda" else "cpu",
            "compute_type": "int8",
            "download_root": WHISPER_MODEL_DIR,
            "local_files_only": not auto_update,
        }

        try:
            whisper_model = WhisperModel(**faster_whisper_kwargs)
        except Exception:
            log.warning(
                "WhisperModel initialization failed, attempting download with local_files_only=False"
            )
            faster_whisper_kwargs["local_files_only"] = False
            whisper_model = WhisperModel(**faster_whisper_kwargs)
    return whisper_model


##########################################
#
# Audio API
#
##########################################


class TTSConfigForm(BaseModel):
    OPENAI_API_BASE_URL: str
    OPENAI_API_KEY: str
    API_KEY: str
    ENGINE: str
    MODEL: str
    VOICE: str
    SPLIT_ON: str
    AZURE_SPEECH_REGION: str
    AZURE_SPEECH_OUTPUT_FORMAT: str


class STTConfigForm(BaseModel):
    OPENAI_API_BASE_URL: str
    OPENAI_API_KEY: str
    ENGINE: str
    MODEL: str
    WHISPER_MODEL: str


class AudioConfigUpdateForm(BaseModel):
    tts: TTSConfigForm
    stt: STTConfigForm


@router.post("/config/update")
async def update_audio_config(
    request: Request, form_data: AudioConfigUpdateForm, user=Depends(get_admin_user)
):
    request.app.state.config.TTS_VOICE = form_data.tts.VOICE

    return {
        "tts": {
            "VOICE": request.app.state.config.TTS_VOICE,
        }
    }


@router.post("/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    subscription = payments_service.get_subscription(user.company_id)

    await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

    body = await request.body()
    name = hashlib.sha256(
        body
    ).hexdigest()

    file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
    file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

    # Check if the file already exists in the cache
    if file_path.is_file():
        return FileResponse(file_path)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    payload["model"] = "TTS"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=f"{os.getenv('OPENAI_API_BASE_URL')}/audio/speech",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                },
            ) as r:
                r.raise_for_status()

                if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                    await credit_service.subtract_credits_by_user_for_tts(user, payload["input"])

                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(await r.read())

                async with aiofiles.open(file_body_path, "w") as f:
                    await f.write(json.dumps(payload))

        return FileResponse(file_path)

    except Exception as e:
        log.exception(e)
        detail = None

        try:
            if r.status != 200:
                res = await r.json()

                if "error" in res:
                    detail = f"External: {res['error'].get('message', '')}"
        except Exception:
            detail = f"External: {e}"

        raise HTTPException(
            status_code=getattr(r, "status", 500),
            detail=detail if detail else "Server Connection Error",
        )


def transcribe(request: Request, file_path):
    log.debug(f"transcribe: {file_path}")
    filename = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    id = filename.split(".")[0]

    if is_mp4_audio(file_path):
        os.rename(file_path, file_path.replace(".wav", ".mp4"))
        # Convert MP4 audio file to WAV format
        convert_mp4_to_wav(file_path.replace(".wav", ".mp4"), file_path)

    r = None

    try:
        audio = AudioSegment.from_file(file_path)
        duration_seconds = len(audio) / 1000.0

        r = requests.post(
            url=f"{os.getenv('OPENAI_API_BASE_URL')}/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
            },
            files={"file": (filename, open(file_path, "rb"))},
            data={"model": "STT", "language": "de"},
        )

        r.raise_for_status()
        data = r.json()
        data["duration"] = duration_seconds

        # save the transcript to a json file
        transcript_file = f"{file_dir}/{id}.json"
        with open(transcript_file, "w") as f:
            json.dump(data, f)

        return data
    except Exception as e:
        log.exception(e)

        detail = None
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    detail = f"External: {res['error'].get('message', '')}"
            except Exception:
                detail = f"External: {e}"

        raise Exception(detail if detail else "Server Connection Error")


def compress_audio(file_path):
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        file_dir = os.path.dirname(file_path)
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(16000).set_channels(1)  # Compress audio
        compressed_path = f"{file_dir}/{id}_compressed.opus"
        audio.export(compressed_path, format="opus", bitrate="32k")
        log.debug(f"Compressed audio to {compressed_path}")

        if (
            os.path.getsize(compressed_path) > MAX_FILE_SIZE
        ):  # Still larger than MAX_FILE_SIZE after compression
            raise Exception(ERROR_MESSAGES.FILE_TOO_LARGE(size=f"{MAX_FILE_SIZE_MB}MB"))
        return compressed_path
    else:
        return file_path


@router.post("/transcriptions")
async def transcription(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    log.info(f"file.content_type: {file.content_type}")

    subscription = payments_service.get_subscription(user.company_id)

    await credit_service.check_for_subscription_and_sufficient_balance_and_seats(user)

    if file.content_type not in ["audio/mpeg", "audio/wav", "audio/ogg", "audio/x-m4a"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_SUPPORTED,
        )

    try:
        ext = file.filename.split(".")[-1]
        id = uuid.uuid4()

        filename = f"{id}.{ext}"
        contents = file.file.read()

        file_dir = f"{CACHE_DIR}/audio/transcriptions"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/{filename}"

        with open(file_path, "wb") as f:
            f.write(contents)

        try:
            try:
                file_path = compress_audio(file_path)
            except Exception as e:
                log.exception(e)

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT(),
                )

            response = transcribe(request, file_path)

            if subscription.get("plan") != "free" and subscription.get("plan") != "premium":
                await credit_service.subtract_credits_by_user_for_stt(user, response)

            file_path = file_path.split("/")[-1]

            return {**response, "filename": file_path}
        except Exception as e:
            log.exception(e)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(),
            )

    except Exception as e:
        log.exception(e)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


def get_available_voices() -> dict:
    """Returns {voice_id: voice_name} dict"""
    available_voices = {
        "alloy": "alloy",
        "echo": "echo",
        "fable": "fable",
        "onyx": "onyx",
        "nova": "nova",
        "shimmer": "shimmer",
    }

    return available_voices

@router.get("/voices")
async def get_voices(request: Request, user=Depends(get_verified_user)):
    return {
        "voices": [
            {"id": k, "name": v} for k, v in get_available_voices().items()
        ]
    }
