import base64
import io
import logging
import os
import uuid

import httpx
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from beyond_the_loop.models.models import ModelForm, ModelMeta, ModelParams, Models
from beyond_the_loop.routers import litellm
from beyond_the_loop.routers.auths import INITIAL_CREDIT_BALANCE
from beyond_the_loop.models.companies import (
    NO_COMPANY,
    Companies,
    CompanyConfigResponse,
    CompanyModel,
    UpdateCompanyConfigRequest,
    UpdateCompanyForm,
    CreateCompanyForm,
)
from open_webui.utils.auth import get_current_user, get_admin_user
from open_webui.env import SRC_LOG_LEVELS
from beyond_the_loop.config import save_config, get_config
from beyond_the_loop.models.users import Users
from beyond_the_loop.services.crm_service import crm_service
from beyond_the_loop.services.loops_service import loops_service

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


############################
# Company Config
############################


@router.get("/config", response_model=CompanyConfigResponse)
async def get_company_config(user=Depends(get_current_user)):
    """
    Get the configuration for the user's company
    
    Args:
        user: The current authenticated user
        
    Returns:
        CompanyConfigResponse: The company configuration
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        # Get the company config from the database
        config = get_config(company_id)

        # Ensure default_models is always set, falling back to DEFAULT_MODEL env var
        if not config.get("models", {}).get("default_models"):
            model = Models.get_model_by_name_and_company(os.getenv("DEFAULT_MODEL"), company_id)
            if "models" not in config:
                config["models"] = {}
            config["models"]["default_models"] = model.id if model else ""

        # Remove security relevant fields
        config.get("audio", {}).get("stt", {}).get("openai", {}).pop("api_key", None)
        config.get("audio", {}).get("tts", {}).get("openai", {}).pop("api_key", None)

        config.get("image_generation", {}).get("openai", {}).pop("api_key", None)

        config.get("rag", {}).pop("openai_api_key", None)

        config.get("rag", {}).get("web", {}).get("search", {}).pop("google_pse_api_key", None)
        config.get("rag", {}).get("web", {}).get("search", {}).pop("google_pse_engine_id", None)

        return {"config": config}
    except Exception as e:
        log.error(f"Error getting company config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting company config: {str(e)}")



@router.post("/config", response_model=CompanyConfigResponse)
async def update_company_config(
    form_data: UpdateCompanyConfigRequest,
    user=Depends(get_admin_user)
):
    """
    Update specific configuration settings for the user's company
    
    Args:
        form_data: The specific configuration settings to update
        user: The current authenticated admin user
        
    Returns:
        CompanyConfigResponse: The updated company configuration
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        # Get the current config
        current_config = get_config(company_id)

        # Update only the specific fields that were provided
        if form_data.hide_model_logo_in_chat is not None:
            if "ui" not in current_config:
                current_config["ui"] = {}
            current_config["ui"]["hide_model_logo_in_chat"] = form_data.hide_model_logo_in_chat
            
        if form_data.chat_retention_days is not None:
            if "data" not in current_config:
                current_config["data"] = {}
            current_config["data"]["chat_retention_days"] = form_data.chat_retention_days
            
        if form_data.custom_user_notice is not None:
            if "ui" not in current_config:
                current_config["ui"] = {}
            current_config["ui"]["custom_user_notice"] = form_data.custom_user_notice
            
        if form_data.features_web_search is not None:
            if "rag" not in current_config:
                current_config["rag"] = {}
            if "web" not in current_config["rag"]:
                current_config["rag"]["web"] = {}
            if "search" not in current_config["rag"]["web"]:
                current_config["rag"]["web"]["search"] = {}
            current_config["rag"]["web"]["search"]["enable"] = form_data.features_web_search
            
        if form_data.features_image_generation is not None:
            if "image_generation" not in current_config:
                current_config["image_generation"] = {}
            current_config["image_generation"]["enable"] = form_data.features_image_generation

        # Save the updated config to the database
        success = save_config(current_config, company_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save company configuration")
        
        # Get the updated config
        updated_config = get_config(company_id)
        
        return {"config": updated_config}
    except Exception as e:
        log.error(f"Error updating company config: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating company config: {str(e)}")



############################
# Company Details
############################

@router.get("/details", response_model=CompanyModel)
async def get_company_details(request: Request, user=Depends(get_current_user)):
    """
    Get details of the user's company
    
    Args:
        request: The FastAPI request object
        user: The current authenticated user
        
    Returns:
        CompanyModel: The company details
    """
    try:
        company_id = user.company_id
        if not company_id or company_id == NO_COMPANY:
            raise HTTPException(status_code=404, detail="Company not found")

        company = Companies.get_company_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        return company
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting company details: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting company details: {str(e)}")



@router.post("/details", response_model=CompanyModel)
async def update_company_details(
    request: Request, 
    form_data: UpdateCompanyForm, 
    user=Depends(get_admin_user)
):
    """
    Update details of the user's company
    
    Args:
        request: The FastAPI request object
        form_data: The company details to update
        user: The current authenticated admin user
        
    Returns:
        CompanyModel: The updated company details
    """
    try:
        company_id = user.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        # Create a dict with only the non-None values
        update_data = {k: v for k, v in form_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        updated_company = Companies.update_company_by_id(company_id, update_data)
        if not updated_company:
            raise HTTPException(status_code=404, detail="Company not found or update failed")
        
        return updated_company
    except Exception as e:
        log.error(f"Error updating company details: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating company details: {str(e)}")


############################
# Company Creation
############################

@router.post("/create", response_model=CompanyModel)
async def create_company(
    form_data: CreateCompanyForm,
    user=Depends(get_current_user),
):
    try:
        company_id = str(uuid.uuid4())

        Companies.create_company(
            {
                "id": company_id,
                "name": form_data.company_name,
                "credit_balance": INITIAL_CREDIT_BALANCE,
                "subdomain": form_data.subdomain,
                "billing_country": form_data.billing_country,
                "profile_image_url": form_data.company_profile_image_url,
            }
        )

        Users.update_company_by_id(user.id, company_id)

        # Save default config for the new company
        from beyond_the_loop.config import save_config, DEFAULT_CONFIG

        save_config(DEFAULT_CONFIG, company_id)

        # Create model entries in DB based on the LiteLLM models
        openai_models = (await litellm.get_all_models_from_litellm())["data"]

        util_models = [
            "TTS",
            "STT"
        ]

        openai_models = [openai_model for openai_model in openai_models if openai_model["id"] not in util_models]

        disabled_models = [
            "Perplexity Sonar Deep Research",
            "Perplexity Sonar Reasoning Pro",
        ]

        # Register OpenAI models in the database if they don't exist
        for model in openai_models:
            Models.insert_new_model(
                ModelForm(
                    id=str(uuid.uuid4()),
                    name=model[
                        "id"
                    ],  # Use ID as name since OpenAI models don't have separate names
                    meta=ModelMeta(
                        description="OpenAI model",
                        profile_image_url="/static/favicon.png",
                    ),
                    params=ModelParams(),
                    access_control=None,  # None means public access
                    is_active=model["id"] not in disabled_models
                ),
                user_id="system",
                company_id=company_id,
            )

        # Create Stripe customer for the new company
        from beyond_the_loop.routers.payments import stripe

        # Create a Stripe customer for the company (without payment details)
        stripe_customer = stripe.Customer.create(
            email=user.email,
            name=form_data.company_name,
            metadata={"company_id": company_id},
        )

        # Update company with Stripe customer ID
        company = Companies.update_company_by_id(
            company_id, {"stripe_customer_id": stripe_customer.id}
        )

        try:
            loops_service.create_or_update_loops_contact(user)
            crm_service.create_company(company_name=company.name, super_admin_email=user.email)
            utm_params = {k: v for k, v in (user.info or {}).items() if k.startswith("utm_")}

            crm_service.create_user(company_name=company.name, user_email=user.email, user_firstname=user.first_name, user_lastname=user.last_name, access_level="Admin", utm_params=utm_params or None)
            crm_service.update_company_super_admin(company_name=company.name, super_admin_email=user.email)
        except Exception as e:
            log.error(f"Failed to create company or user in CRM or in Loops: {e}")

        return company

    except Exception as e:
        log.error(f"Error creating company: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating company: {str(e)}"
        )


############################
# Company Logo Lookup
############################

@router.get("/logo")
async def get_company_logo(email: str = Query(...)):

    """
    Fetch a company logo by email domain via Google Favicon.
    Returns {"logo": "<base64 data URL>"} or {"logo": ""}.
    """
    domain = email.split("@")[-1].strip().lower() if "@" in email else ""
    if not domain:
        return JSONResponse({"logo": ""})

    async with httpx.AsyncClient(timeout=10) as client:
        logo = await _fetch_as_data_url(
            client,
            f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        )
        return JSONResponse({"logo": logo})


async def _fetch_as_data_url(client: httpx.AsyncClient, url: str) -> str:
    _GOOGLE_DEFAULT_FAVICON = "data:image/png;base64,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"
    try:
        res = await client.get(url, follow_redirects=True)
        if res.status_code != 200:
            return ""
        content_type = res.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            return ""
        if len(res.content) < 100:
            return ""

        # Reject transparent PNGs (no solid background = not a real logo)
        try:
            img = Image.open(io.BytesIO(res.content))
            if img.mode in ("RGBA", "LA", "PA"):
                alpha = img.getchannel("A")
                if min(alpha.getdata()) < 128:
                    return ""
        except Exception:
            pass

        b64 = base64.b64encode(res.content).decode()
        result = f"data:{content_type};base64,{b64}"
        if result == _GOOGLE_DEFAULT_FAVICON:
            return ""
        return result
    except Exception:
        return ""