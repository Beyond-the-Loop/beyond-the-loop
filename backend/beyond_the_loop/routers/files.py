import io
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from beyond_the_loop.utils.file_conversion import convert_for_rag
from beyond_the_loop.utils.file_upload_validator import FileValidator

from beyond_the_loop.storage.provider import Storage
from beyond_the_loop.retrieval.rag_engine import (
    get_google_rag_client,
    rag_file_to_file_meta,
)
from beyond_the_loop.services.file_service import delete_file_fully

from beyond_the_loop.models.files import (
    FileForm,
    FileModel,
    FileModelResponse,
    Files,
)
from beyond_the_loop.models.users import Users
from open_webui.env import SRC_LOG_LEVELS
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from fastapi.responses import FileResponse, StreamingResponse
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


router = APIRouter()

############################
# Upload File
############################


@router.post("/", response_model=FileModelResponse)
def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_verified_user)
):
    t_request_start = time.perf_counter()
    log.info(
        "[UPLOAD_TIMING] step=request_start filename=%s content_type=%s",
        file.filename,
        file.content_type,
    )
    try:
        unsanitized_filename = file.filename
        filename = os.path.basename(unsanitized_filename)

        t0 = time.perf_counter()
        FileValidator.validate_upload(file)
        log.info(
            "[UPLOAD_TIMING] step=validate_upload duration_ms=%.2f",
            (time.perf_counter() - t0) * 1000,
        )

        # Convert non-RAG-supported file types (e.g. .py -> .txt) before upload
        t0 = time.perf_counter()
        file.file.seek(0)
        original_bytes = file.file.read()
        converted_bytes, name = convert_for_rag(original_bytes, filename)
        log.info(
            "[UPLOAD_TIMING] step=convert_for_rag duration_ms=%.2f original=%s converted=%s",
            (time.perf_counter() - t0) * 1000,
            filename,
            name,
        )

        # replace filename with uuid (using converted name so storage matches)
        id = str(uuid.uuid4())
        filename = f"{id}_{name}"

        t0 = time.perf_counter()
        contents, file_path = Storage.upload_file(io.BytesIO(converted_bytes), filename)
        log.info(
            "[UPLOAD_TIMING] step=storage_upload duration_ms=%.2f size_bytes=%d file_path=%s",
            (time.perf_counter() - t0) * 1000,
            len(contents),
            file_path,
        )

        t0 = time.perf_counter()
        file_item = Files.insert_new_file(
            user.id,
            FileForm(
                **{
                    "id": id,
                    "filename": name,
                    "path": file_path,
                    "meta": {
                        "name": name,
                        "content_type": file.content_type,
                        "size": len(contents),
                    },
                }
            ),
        )
        log.info(
            "[UPLOAD_TIMING] step=db_insert_new_file duration_ms=%.2f id=%s",
            (time.perf_counter() - t0) * 1000,
            id,
        )

        try:
            t0 = time.perf_counter()
            google_rag = get_google_rag_client()
            log.info(
                "[UPLOAD_TIMING] step=get_google_rag_client duration_ms=%.2f",
                (time.perf_counter() - t0) * 1000,
            )

            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(name)[1] or None,
                delete=True,
            ) as tmp:
                t0 = time.perf_counter()
                tmp.write(contents)
                tmp.flush()
                log.info(
                    "[UPLOAD_TIMING] step=write_tempfile duration_ms=%.2f path=%s",
                    (time.perf_counter() - t0) * 1000,
                    tmp.name,
                )

                t0 = time.perf_counter()
                rag_file = google_rag.upload_file_to_corpus(tmp.name, display_name=filename)
                log.info(
                    "[UPLOAD_TIMING] step=rag_upload_file_to_corpus duration_ms=%.2f rag_file=%s",
                    (time.perf_counter() - t0) * 1000,
                    getattr(rag_file, "name", "<unknown>"),
                )

            t0 = time.perf_counter()
            file_item = Files.update_file_metadata_by_id(
                id,
                rag_file_to_file_meta(
                    rag_file,
                    corpus=google_rag.corpus,
                    gcs_uri=file_path,
                ),
            )
            log.info(
                "[UPLOAD_TIMING] step=db_update_metadata duration_ms=%.2f id=%s",
                (time.perf_counter() - t0) * 1000,
                id,
            )
            log.info(
                "Uploaded file %s into Google RAG Engine as %s",
                id,
                rag_file.name,
            )
        except Exception as e:
            log.error(f"Error uploading file {id} into Google RAG Engine: {e}")
            Files.update_file_metadata_by_id(
                id,
                {
                    "rag_provider": "google",
                    "rag_gcs_uri": file_path,
                    "rag_import_status": "failed",
                    "rag_import_error": str(e),
                },
            )
            file_item = FileModelResponse(
                **{
                    **file_item.model_dump(),
                    "error": str(e),
                }
            )

        log.info(
            "[UPLOAD_TIMING] step=request_total duration_ms=%.2f id=%s",
            (time.perf_counter() - t_request_start) * 1000,
            id,
        )

        if file_item:
            return file_item
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT,
            )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT,
        )


############################
# Get File By Id
############################


@router.get("/{id}", response_model=Optional[FileModel])
async def get_file_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        return file
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

############################
# Get File Content By Id
############################


@router.get("/{id}/content")
async def get_file_content_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    file_user = Users.get_user_by_id(file.user_id)
    if not (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        file_path = Path(Storage.get_file(file.path))

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        filename = file.meta.get("name", file.filename)
        encoded_filename = quote(filename)

        headers = {}
        if file.meta.get("content_type") not in ["application/pdf", "text/plain"]:
            headers["Content-Disposition"] = (
                f"attachment; filename*=UTF-8''{encoded_filename}"
            )

        return FileResponse(file_path, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
        )


@router.get("/{id}/content/{file_name}")
async def get_file_content_by_id_with_name(id: str, file_name: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    file_user = Users.get_user_by_id(file.user_id)
    if not (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    try:
        file_path = Path(Storage.get_file(file.path))

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        filename = file.meta.get("name", file.filename)
        encoded_filename = quote(filename)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }

        return FileResponse(file_path, headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
        )


############################
# Delete File By Id
############################


@router.delete("/{id}")
async def delete_file_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        try:
            delete_file_fully(file)
        except Exception as e:
            log.exception(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting file"),
            )

        return {"message": "File deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
