import logging
from typing import Optional
from beyond_the_loop.models.groups import (
    Groups,
    GroupForm,
    GroupUpdateForm,
    GroupResponse,
)

log = logging.getLogger(__name__)

def normalize_workspace_permissions(form_data: GroupForm) -> None:
    """
    Ensures that edit permissions automatically grant corresponding view permissions.
    If a user has edit_prompts permission, they also get view_prompts permission.
    If a user has edit_assistants permission, they also get view_assistants permission.
    """
    if form_data.permissions:
        if form_data.permissions.get("workspace", {}).get("edit_prompts", False):
            form_data.permissions["workspace"]["view_prompts"] = True
            
        if form_data.permissions.get("workspace", {}).get("edit_assistants", False):
            form_data.permissions["workspace"]["view_assistants"] = True

        if form_data.permissions.get("workspace", {}).get("edit_knowledge", False):
            form_data.permissions["workspace"]["view_knowledge"] = True


from beyond_the_loop.models.users import Users

from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, status
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()

############################
# GetFunctions
############################


@router.get("/", response_model=list[GroupResponse])
async def get_groups(user=Depends(get_verified_user)):
    if user.role == "admin":
        return Groups.get_groups_by_company(user.company_id)
    else:
        return Groups.get_groups_by_member_id(user.id)


############################
# CreateNewGroup
############################


@router.post("/create", response_model=Optional[GroupResponse])
async def create_new_function(form_data: GroupForm, user=Depends(get_admin_user)):
    try:
        if not form_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Group name is required"),
            )

        normalize_workspace_permissions(form_data)

        group = Groups.insert_new_group(user.company_id, form_data)

        if group:
            return group
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error creating group"),
            )
    except Exception as e:
        log.error(f"Error creating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


############################
# GetGroupById
############################


@router.get("/id/{id}", response_model=Optional[GroupResponse])
async def get_group_by_id(id: str, user=Depends(get_admin_user)):
    group = Groups.get_group_by_id(id)
    if group:
        return group
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateGroupById
############################


@router.post("/id/{id}/update", response_model=Optional[GroupResponse])
async def update_group_by_id(
    id: str, form_data: GroupUpdateForm, user=Depends(get_admin_user)
):
    try:
        if not form_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Group name is required"),
            )

        if form_data.user_ids:
            form_data.user_ids = Users.get_valid_user_ids(form_data.user_ids)

        normalize_workspace_permissions(form_data)

        group = Groups.update_group_by_id(id, form_data)

        if group:
            return group
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating group"),
            )
    except Exception as e:
        log.error(f"Error updating group: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


############################
# DeleteGroupById
############################


@router.delete("/id/{id}/delete", response_model=bool)
async def delete_group_by_id(id: str, user=Depends(get_admin_user)):
    try:
        result = Groups.delete_group_by_id(id)
        if result:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting group"),
            )
    except Exception as e:
        log.error(f"Error deleting group: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )
