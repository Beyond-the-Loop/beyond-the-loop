from typing import Optional

from beyond_the_loop.models.prompts import (
    PromptForm,
    PromptUserResponse,
    PromptModel,
    Prompts, TagResponse
)
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, status, Request
from open_webui.utils.auth import get_verified_user
from beyond_the_loop.utils.access_control import has_access, has_permission

router = APIRouter()


def _validate_prompt_write_access(prompt: PromptModel, user):
    """
    Validates that a user has write access to a prompt.
    Raises HTTPException if access is denied.
    """
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if prompt.prebuilt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if (user.role != "admin"
            and prompt.user_id != user.id
            and not has_access(user.id, "write", prompt.access_control)
            and not has_permission(user.id, "workspace.edit_prompts")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

def _validate_prompt_read_access(prompt: PromptModel, user):
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if (user.role != "admin"
            and prompt.user_id != user.id
            and not has_access(user.id, "read", prompt.access_control)
            and not has_permission(user.id, "workspace.view_prompts")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


############################
# GetPrompts
############################


@router.get("/", response_model=list[PromptModel])
async def get_prompts(user=Depends(get_verified_user)):
    if not has_permission(user.id, "workspace.view_prompts"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    return Prompts.get_prompts_by_user_and_company(user.id, user.company_id, "read")


@router.get("/list", response_model=list[PromptUserResponse])
async def get_prompt_list(user=Depends(get_verified_user)):
    if not has_permission(user.id, "workspace.view_prompts"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    prompts = Prompts.get_prompts_by_user_and_company(user.id, user.company_id, "read")
    sorted_prompts = sorted(prompts, key=lambda m: not m.bookmarked_by_user)
    return sorted_prompts


############################
# CreateNewPrompt
############################


@router.post("/create", response_model=Optional[PromptModel])
async def create_new_prompt(
    form_data: PromptForm, user=Depends(get_verified_user)
):
    if not has_permission(user.id, "workspace.view_prompts"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED(),
        )

    prompt = Prompts.get_prompt_by_command_and_company(form_data.command, user.company_id)

    if prompt is None:
        prompt = Prompts.insert_new_prompt(user.id, user.company_id, form_data)

        if prompt:
            return prompt
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.COMMAND_TAKEN(),
    )


############################
# GetPromptByCommand
############################


@router.get("/command/{command}", response_model=Optional[PromptModel])
async def get_prompt_by_command(command: str, user=Depends(get_verified_user)):
    prompt = Prompts.get_prompt_by_command_and_company(f"/{command}", user.company_id)

    _validate_prompt_read_access(prompt, user)

    return prompt


@router.post("/command/{command}/bookmark/update")
async def update_prompt_bookmark(command: str, user=Depends(get_verified_user)):
    prompt = Prompts.get_prompt_by_command_and_company_or_system(f"/{command}", user.company_id)

    _validate_prompt_read_access(prompt, user)

    bookmarked_prompt = Prompts.toggle_bookmark(prompt.command, user.id)

    return {"prompt_command": prompt.command, "bookmarked_by_user": bookmarked_prompt}

############################
# UpdatePromptByCommand
############################


@router.post("/command/{command}/update", response_model=Optional[PromptModel])
async def update_prompt_by_command(
    command: str,
    form_data: PromptForm,
    user=Depends(get_verified_user),
):
    prompt = Prompts.get_prompt_by_command_and_company(f"/{command}", user.company_id)

    _validate_prompt_write_access(prompt, user)

    prompt = Prompts.update_prompt_by_command_and_company(f"/{command}", form_data, user.company_id)

    if prompt:
        return prompt
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.COMMAND_TAKEN,
        )


############################
# DeletePromptByCommand
############################


@router.delete("/command/{command}/delete", response_model=bool)
async def delete_prompt_by_command(
        command: str,
        user=Depends(get_verified_user)
):
    prompt = Prompts.get_prompt_by_command_and_company(f"/{command}", user.company_id)

    _validate_prompt_write_access(prompt, user)

    result = Prompts.delete_prompt_by_command_and_company(f"/{command}", user.company_id)

    return result

############################
# GetTags
############################

@router.get("/tags", response_model=list[TagResponse])
async def get_tags(user=Depends(get_verified_user)):
    tags = Prompts.get_system_and_user_tags(user.id)
    if not tags:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return tags