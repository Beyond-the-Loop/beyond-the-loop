import logging
import os
import tempfile
import uuid
from typing import Optional
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
    log.info(f"file.content_type: {file.content_type}")
    try:
        unsanitized_filename = file.filename
        filename = os.path.basename(unsanitized_filename)

        FileValidator.validate_upload(file)

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
            google_rag = get_google_rag_client()
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(name)[1] or None,
                delete=True,
            ) as tmp:
                tmp.write(contents)
                tmp.flush()
                rag_file = google_rag.upload_file_to_corpus(tmp.name, display_name=filename)
            file_item = Files.update_file_metadata_by_id(
                id,
                rag_file_to_file_meta(
                    rag_file,
                    corpus=google_rag.corpus,
                    gcs_uri=file_path,
                ),
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
