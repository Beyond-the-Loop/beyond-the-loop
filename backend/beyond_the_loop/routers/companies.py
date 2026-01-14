import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from beyond_the_loop.models.models import ModelForm, ModelMeta, ModelParams, Models
from beyond_the_loop.routers import openai
from beyond_the_loop.routers.auths import INITIAL_CREDIT_BALANCE
from beyond_the_loop.models.companies import (
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
from beyond_the_loop.services.payments_service import payments_service
from beyond_the_loop.socket.main import COMPANY_CONFIG_CACHE

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
        if not company_id:
            raise HTTPException(status_code=400, detail="User is not associated with a company")
        
        company = Companies.get_company_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return company
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
    request: Request,
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
                "size": form_data.company_size,
                "industry": form_data.company_industry,
                "team_function": form_data.company_team_function,
                "profile_image_url": form_data.company_profile_image_url,
            }
        )

        Users.update_company_by_id(user.id, company_id)

        # Save default config for the new company
        from beyond_the_loop.config import save_config, DEFAULT_CONFIG

        save_config(DEFAULT_CONFIG, company_id)

        # Create model entries in DB based on the LiteLLM models
        openai_models = await openai.get_all_models()

        openai_models = openai_models["data"]

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
                user_id=None,
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
            crm_service.create_company(company_name=company.name)
            crm_service.create_user(company_name=company.name, user_email=user.email, user_firstname=user.first_name, user_lastname=user.last_name, access_level="Admin")
        except Exception as e:
            log.error(f"Failed to create company or user in CRM or in Loops: {e}")

        return company

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating company: {str(e)}"
        )
