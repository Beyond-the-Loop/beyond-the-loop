import uuid
from typing import Optional

from beyond_the_loop.models.models import (
    ModelForm,
    ModelModel,
    ModelResponse,
    ModelUserResponse,
    Models,
    TagResponse
)
from beyond_the_loop.models.knowledge import Knowledges
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, status

from open_webui.utils.auth import get_verified_user
from beyond_the_loop.utils.access_control import has_access, has_permission
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.routers.knowledge import validate_knowledge_read_access

router = APIRouter()


def _validate_model_write_access(model: ModelModel, user):
    """
    Validates that a user has permission to edit/delete a model.
    
    Args:
        model: The model to check permissions for
        user: The user attempting the operation
        request: FastAPI request object for permission checking
        operation: Either "edit" or "delete" for appropriate error messages
    
    Raises:
        HTTPException: If user lacks required permissions
    """
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    # Avoid editing prebuilt models
    if model.user_id == "system":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if (is_free_user
        or user.role != "admin"
        and model.user_id != user.id
        and (not has_access(user.id, "write", model.access_control) or not has_permission(user.id, "workspace.edit_assistants"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

def _validate_model_read_access(model: ModelModel, user):
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if (is_free_user
            or user.role != "admin"
            and model.user_id != user.id
            and (not has_access(user.id, "read", model.access_control) or not has_permission(user.id,"workspace.view_assistants"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

###########################
# GetModels
###########################


@router.get("/", response_model=list[ModelUserResponse])
async def get_models(user=Depends(get_verified_user)):
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    return Models.get_assistants_by_user_and_company(user.id, user.company_id)


############################
# CreateNewModel
############################


@router.post("/create", response_model=Optional[ModelModel])
async def create_new_model(
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    is_free_user = payments_service.get_subscription(user.company_id).get("plan") == "free"

    if is_free_user or not has_permission(user.id, "workspace.view_assistants"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    model = Models.get_model_by_name_and_company(form_data.name, user.company_id)

    if model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Model already exists"),
        )

    form_data.id = str(uuid.uuid4())

    knowledge = Knowledges.get_knowledge_by_ids([knowledge.get("id", "") for knowledge in form_data.meta.knowledge]) if form_data.meta.knowledge else []

    for k in knowledge:
        validate_knowledge_read_access(k, user)

    model = Models.insert_new_model(form_data, user.id, user.company_id)

    if model:
        return model
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT,
        )


###########################
# GetModelById
###########################


# Note: We're not using the typical url path param here, but instead using a query parameter to allow '/' in the id
@router.get("/model", response_model=Optional[ModelResponse])
async def get_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)

    _validate_model_read_access(model, user)

    model.meta.knowledge = Knowledges.get_knowledge_by_ids([knowledge.get("id", "") for knowledge in model.meta.knowledge]) if model.meta.knowledge else None

    return model


############################
# ToggelModelById
############################


@router.post("/model/toggle", response_model=Optional[ModelResponse])
async def toggle_model_by_id(id: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(id)

    _validate_model_write_access(model, user)

    if (
        model.user_id == user.id
        or has_access(user.id, "write", model.access_control)
    ):
        model = Models.toggle_model_by_id_and_company(id, user.company_id)

        if model:
            return model
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

#################################
# Add and remove from bookmarked
#################################

@router.post("/model/{model}/bookmark/update")
async def update_model_bookmark(model: str, user=Depends(get_verified_user)):
    model = Models.get_model_by_id(model)

    _validate_model_read_access(model, user)

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    bookmarked =Models.toggle_bookmark(model.id, user.id)
    return {"model_id": model.id, "bookmarked_by_user": bookmarked}

############################
# UpdateModelById
############################

@router.post("/model/update", response_model=Optional[ModelModel])
async def update_model_by_id(
    id: str,
    form_data: ModelForm,
    user=Depends(get_verified_user),
):
    model = Models.get_model_by_id(id)

    _validate_model_write_access(model, user)

    # For base models these parameters are not allowed to be edited
    if not model.base_model_id:
        del form_data.base_model_id
        del form_data.id
        del form_data.name

    try:
        knowledge = Knowledges.get_knowledge_by_ids([knowledge.get("id", "") for knowledge in form_data.meta.knowledge]) if form_data.meta.knowledge else []

        for k in knowledge:
            validate_knowledge_read_access(k, user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing assistant with knowledge: {e}")

    updated_model = Models.update_model_by_id_and_company(id, form_data, user.company_id)

    return updated_model


############################
# DeleteModelById
############################


@router.delete("/model/delete", response_model=bool)
async def delete_model_by_id(
        id: str, user=Depends(get_verified_user)
):
    model = Models.get_model_by_id(id)

    # Base models can not be deleted
    if not model.base_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    _validate_model_write_access(model, user)

    updated_model = Models.delete_model_by_id_and_company(id, user.company_id)
    return updated_model

############################
# GetTags
############################

@router.get("/tags", response_model=list[TagResponse])
async def get_tags(user=Depends(get_verified_user)):
    tags = Models.get_system_and_user_tags(user.id)
    if not tags:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return tags