from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Request
import logging

from beyond_the_loop.models.knowledge import KnowledgeModel
from beyond_the_loop.models.knowledge import (
    Knowledges,
    KnowledgeForm,
    KnowledgeResponse,
    KnowledgeUserResponse,
)
from beyond_the_loop.models.files import Files, FileModel

from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import get_verified_user
from beyond_the_loop.models.groups import Groups
from beyond_the_loop.utils.access_control import has_access, has_permission


from open_webui.env import SRC_LOG_LEVELS
from beyond_the_loop.models.models import Models, ModelForm
from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


############################
# getKnowledgeBases
############################

def _validate_knowledge_write_access(knowledge: KnowledgeModel, user, user_groups):
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if (is_free_user
            or user.role != "admin"
            and knowledge.user_id != user.id
            and (not has_access(user.id, user_groups, "write", knowledge.access_control) or not has_permission(user.id, "workspace.edit_knowledge"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

def validate_knowledge_read_access(knowledge: KnowledgeModel, user, user_groups):
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if (is_free_user
            or user.role != "admin"
            and knowledge.user_id != user.id
            and (not has_access(user.id, user_groups, "read", knowledge.access_control) or not has_permission(user.id, "workspace.view_knowledge"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


@router.get("/", response_model=list[KnowledgeUserResponse])
async def get_knowledge(user=Depends(get_verified_user)):
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user or not has_permission(user.id, "workspace.view_knowledge"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    knowledge_bases = Knowledges.get_knowledge_bases_by_user_and_company(user.id, user.company_id, "read")

    # Batch-fetch all files in one query instead of N separate queries
    all_file_ids = []
    for kb in knowledge_bases:
        if kb.data:
            all_file_ids.extend(kb.data.get("file_ids", []))
    all_files_map = {f.id: f for f in Files.get_file_metadatas_by_ids(list(set(all_file_ids)))}

    # Batch models lookup: one company query + Python filter instead of N JSONB queries
    all_company_models = Models.get_all_models_by_company(user.company_id)
    models_by_knowledge_id: dict = {}
    for model in all_company_models:
        if model.meta and model.meta.knowledge:
            for k in model.meta.knowledge:
                kid = k.get("id")
                if kid:
                    models_by_knowledge_id.setdefault(kid, []).append(model)

    knowledge_with_files = []
    for knowledge_base in knowledge_bases:
        kb_file_ids = knowledge_base.data.get("file_ids", []) if knowledge_base.data else []
        files = [all_files_map[fid] for fid in kb_file_ids if fid in all_files_map]

        # Clean up stale file references in one pass
        missing_ids = [fid for fid in kb_file_ids if fid not in all_files_map]
        if missing_ids:
            updated_ids = [fid for fid in kb_file_ids if fid in all_files_map]
            data = knowledge_base.data or {}
            data["file_ids"] = updated_ids
            Knowledges.update_knowledge_data_by_id(id=knowledge_base.id, data=data)

        models = models_by_knowledge_id.get(knowledge_base.id, [])

        knowledge_with_files.append(
            KnowledgeUserResponse(
                **knowledge_base.model_dump(),
                files=files,
                models=models
            )
        )

    return knowledge_with_files


@router.get("/list", response_model=list[KnowledgeUserResponse])
async def get_knowledge_list(user=Depends(get_verified_user)):
    return await get_knowledge(user)


############################
# CreateNewKnowledge
############################


@router.post("/create", response_model=Optional[KnowledgeResponse])
async def create_new_knowledge(
    form_data: KnowledgeForm, user=Depends(get_verified_user)
):
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user or (user.role != "admin" and not has_permission(user.id, "workspace.edit_knowledge")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    knowledge = Knowledges.insert_new_knowledge(user.id, form_data, user.company_id)

    if knowledge:
        return knowledge
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_EXISTS,
        )


############################
# GetKnowledgeById
############################


class KnowledgeFilesResponse(KnowledgeResponse):
    files: list[FileModel]


@router.get("/{id}", response_model=Optional[KnowledgeFilesResponse])
async def get_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    knowledge = Knowledges.get_knowledge_by_id(id=id)

    user_groups = Groups.get_groups_by_member_id(user.id)
    validate_knowledge_read_access(knowledge, user, user_groups)

    file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
    files = Files.get_files_by_ids(file_ids)

    return KnowledgeFilesResponse(
        **knowledge.model_dump(),
        files=files
    )


############################
# UpdateKnowledgeById
############################


@router.post("/{id}/update", response_model=Optional[KnowledgeFilesResponse])
async def update_knowledge_by_id(
    id: str,
    form_data: KnowledgeForm,
    user=Depends(get_verified_user),
):
    knowledge = Knowledges.get_knowledge_by_id(id=id)

    user_groups = Groups.get_groups_by_member_id(user.id)
    _validate_knowledge_write_access(knowledge, user, user_groups)

    knowledge = Knowledges.update_knowledge_by_id(id=id, form_data=form_data)

    if knowledge:
        file_ids = knowledge.data.get("file_ids", []) if knowledge.data else []
        files = Files.get_files_by_ids(file_ids)

        return KnowledgeFilesResponse(
            **knowledge.model_dump(),
            files=files,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ID_TAKEN,
        )


class KnowledgeFileIdForm(BaseModel):
    file_id: str


############################
# DeleteKnowledgeById
############################


@router.delete("/{id}/delete", response_model=bool)
async def delete_knowledge_by_id(id: str, user=Depends(get_verified_user)):
    knowledge = Knowledges.get_knowledge_by_id(id=id)

    user_groups = Groups.get_groups_by_member_id(user.id)
    _validate_knowledge_write_access(knowledge, user, user_groups)

    log.info(f"Deleting knowledge base: {id} (name: {knowledge.name})")

    # Get all models
    models = Models.get_all_models_by_company(user.company_id)
    log.info(f"Found {len(models)} models to check for knowledge base {id}")

    # Update models that reference this knowledge base
    for model in models:
        if model.meta and hasattr(model.meta, "knowledge"):
            knowledge_list = model.meta.knowledge or []
            # Filter out the deleted knowledge base
            updated_knowledge = [k for k in knowledge_list if k.get("id") != id]

            # If the knowledge list changed, update the model
            if len(updated_knowledge) != len(knowledge_list):
                log.info(f"Updating model {model.id} to remove knowledge base {id}")
                model.meta.knowledge = updated_knowledge
                # Create a ModelForm for the update
                model_form = ModelForm(
                    id=model.id,
                    name=model.name,
                    base_model_id=model.base_model_id,
                    meta=model.meta,
                    params=model.params,
                    access_control=model.access_control,
                    is_active=model.is_active
                )

                Models.update_model_by_id_and_company(model.id, model_form, user.company_id)

    return Knowledges.delete_knowledge_by_id(id=id)



