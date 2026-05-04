import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from urllib.parse import quote

from beyond_the_loop.storage.provider import Storage
from beyond_the_loop.retrieval.rag_engine import GoogleRagEngineClient

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
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user)
):
    log.info(f"file.content_type: {file.content_type}")
    try:
        unsanitized_filename = file.filename
        filename = os.path.basename(unsanitized_filename)

        # replace filename with uuid
        id = str(uuid.uuid4())
        name = filename
        filename = f"{id}_{filename}"
        contents, file_path = Storage.upload_file(file.file, filename)

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

        try:
            google_rag = GoogleRagEngineClient()
            rag_file = google_rag.import_gcs_file(file_path)
            file_item = Files.update_file_metadata_by_id(
                id,
                rag_file.to_file_meta(
                    corpus=google_rag.corpus,
                    gcs_uri=file_path,
                ),
            )
            log.info(
                "Imported file %s into Google RAG Engine as %s",
                id,
                rag_file.name,
            )
        except Exception as e:
            log.error(f"Error importing file {id} into Google RAG Engine: {e}")
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

        if file_item:
            return file_item
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT,
            )

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
# Get File Data Content By Id
############################


@router.get("/{id}/data/content")
async def get_file_data_content_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        return {"content": file.data.get("content", "")}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Update File Data Content By Id
############################


class ContentForm(BaseModel):
    content: str


@router.post("/{id}/data/content/update")
async def update_file_data_content_by_id(
    request: Request, id: str, form_data: ContentForm, user=Depends(get_verified_user)
):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Updating extracted file content is not supported with Google RAG Engine. Re-upload the file instead.",
        )
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
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        try:
            file_path = Storage.get_file(file.path)
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                # Handle Unicode filenames
                filename = file.meta.get("name", file.filename)
                encoded_filename = quote(filename)  # RFC5987 encoding

                headers = {}
                if file.meta.get("content_type") not in [
                    "application/pdf",
                    "text/plain",
                ]:
                    headers = {
                        **headers,
                        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    }

                return FileResponse(file_path, headers=headers)

            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        except Exception as e:
            log.exception(e)
            log.error(f"Error getting file content")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.get("/{id}/content/{file_name}")
async def get_file_content_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        file_path = file.path

        # Handle Unicode filenames
        filename = file.meta.get("name", file.filename)
        encoded_filename = quote(filename)  # RFC5987 encoding
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }

        if file_path:
            file_path = Storage.get_file(file_path)
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                return FileResponse(file_path, headers=headers)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        else:
            # File path doesn’t exist, return the content as .txt if possible
            file_content = file.content.get("content", "")
            file_name = file.filename

            # Create a generator that encodes the file content
            def generator():
                yield file_content.encode("utf-8")

            return StreamingResponse(
                generator(),
                media_type="text/plain",
                headers=headers,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# Delete File By Id
############################


@router.delete("/{id}")
async def delete_file_by_id(id: str, user=Depends(get_verified_user)):
    file = Files.get_file_by_id(id)
    file_user = Users.get_user_by_id(file.user_id)

    if file and (file.user_id == user.id or (user.role == "admin" and file_user.company_id == user.company_id)):
        # We should add Chroma cleanup here

        result = Files.delete_file_by_id(id)
        if result:
            try:
                Storage.delete_file(file.path)
            except Exception as e:
                log.exception(e)
                log.error(f"Error deleting files")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error deleting files"),
                )
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting file"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
