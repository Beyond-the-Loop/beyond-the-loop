from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from typing import Optional

from open_webui.utils.auth import get_admin_user, get_verified_user
from beyond_the_loop.config import get_config, save_config


router = APIRouter()



############################
# SetDefaultModels
############################
class ModelsConfigForm(BaseModel):
    DEFAULT_MODELS: Optional[str]
    MODEL_ORDER_LIST: Optional[list[str]]


@router.get("/models", response_model=ModelsConfigForm)
async def get_models_config(request: Request, user=Depends(get_admin_user)):
    current_config = get_config(user.company_id)

    return {
        "DEFAULT_MODELS": current_config.get("models", {}).get("default_models"),
        "MODEL_ORDER_LIST": request.app.state.config.MODEL_ORDER_LIST,
    }


@router.post("/models", response_model=ModelsConfigForm)
async def set_models_config(
    request: Request, form_data: ModelsConfigForm, user=Depends(get_admin_user)
):
    # Get company_id from the authenticated user
    company_id = user.company_id

    # Get current config and update it
    current_config = get_config(company_id)
    if "models" not in current_config:
        current_config["models"] = {}
    current_config["models"]["default_models"] = form_data.DEFAULT_MODELS

    # Save the updated config
    save_config(current_config, company_id)
    
    return {
        "DEFAULT_MODELS": form_data.DEFAULT_MODELS,
        "MODEL_ORDER_LIST": form_data.MODEL_ORDER_LIST,
    }


class PromptSuggestion(BaseModel):
    title: list[str]
    content: str


class SetDefaultSuggestionsForm(BaseModel):
    suggestions: list[PromptSuggestion]


@router.post("/suggestions", response_model=list[PromptSuggestion])
async def set_default_suggestions(
    request: Request, form_data: SetDefaultSuggestionsForm, user=Depends(get_admin_user)
):
    # Get company_id from the authenticated user
    company_id = user.company_id
    
    data = form_data.model_dump()
    request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS = data["suggestions"]
    
    # Get current config and update it
    current_config = get_config(company_id)
    if "ui" not in current_config:
        current_config["ui"] = {}
    current_config["ui"]["prompt_suggestions"] = data["suggestions"]
    
    # Save the updated config
    save_config(current_config, company_id)
    
    return request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS
