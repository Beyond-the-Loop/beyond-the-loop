import hashlib
import logging
import random
import uuid
from typing import Optional

from beyond_the_loop.retrieval.vector.connector import VECTOR_DB_CLIENT
from beyond_the_loop.storage.provider import Storage
from beyond_the_loop.models.users import UserInviteForm, UserCreateForm
from beyond_the_loop.models.auths import Auths
from beyond_the_loop.models.files import Files
from beyond_the_loop.models.groups import Groups, GroupForm
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.models import Models
from beyond_the_loop.models.prompts import Prompts
from beyond_the_loop.models.knowledge import Knowledges
from beyond_the_loop.models.users import (
    UserModel,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
    UserReinviteForm,
    UserRevokeInviteForm
)


from beyond_the_loop.socket.main import get_active_status_by_user_id, COMPANY_CONFIG_CACHE, STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE, STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from open_webui.utils.auth import get_admin_user, get_password_hash, get_verified_user
from open_webui.utils.misc import validate_email_format, is_business_email
from beyond_the_loop.services.email_service import EmailService
from beyond_the_loop.utils.access_control import DEFAULT_USER_PERMISSIONS
from beyond_the_loop.services.crm_service import crm_service
from beyond_the_loop.services.loops_service import loops_service

from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

NEW_INDICATOR = "NEW"
INVITED_INDICATOR = "INVITED"

@router.post("/invite")
async def invite_user(form_data: UserInviteForm, user=Depends(get_admin_user)):
    validation_errors = []
    
    try:
        # Get the active subscription to check seat limits
        from beyond_the_loop.routers.payments import get_subscription
        from beyond_the_loop.models.users import Users

        company = Companies.get_company_by_id(user.company_id)

        subscription_details = get_subscription(user)

        if not company.subscription_not_required and not subscription_details.get("plan") == "free" and not subscription_details.get("plan") == "premium":
            # Get subscription details
            subscription_details = get_subscription(user)

            # Get current seat count and limit
            seats_limit = subscription_details.get("seats", 0)
            seats_taken = subscription_details.get("seats_taken", 0)

            # Calculate how many seats are available
            available_seats = max(0, seats_limit - seats_taken)

            # Check if there are enough seats for all invitees
            if len(form_data.invitees) > available_seats:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough seats available in your subscription. You have {available_seats} seats available but are trying to invite {len(form_data.invitees)} users. Please upgrade your plan or remove some users."
                )

        # Validate all invitees first
        if not form_data.invitees:
            raise HTTPException(
                status_code=400,
                detail="No invitees provided"
            )
            
        # First pass: validate all emails without making any changes
        for invitee in form_data.invitees:
            email = invitee.email.lower()
            
            # Validate email format
            if not validate_email_format(email):
                validation_errors.append({"reason": f"{email} is invalid. {ERROR_MESSAGES.INVALID_EMAIL_FORMAT}"})
                continue

            # Reject personal/consumer email domains
            # Exception: some companies are allowed to invite non-business emails
            COMPANIES_ALLOWED_NON_BUSINESS_EMAILS = {"1f62d141-5b4f-4ebf-8468-83bab4765c1b", "bed374b4-bd32-42f6-8cd0-0767bbe7fdc5", "bdc018de-359c-480b-aa44-b7d9c47a5b4c"}
            if user.company_id not in COMPANIES_ALLOWED_NON_BUSINESS_EMAILS and not is_business_email(email):
                validation_errors.append({"reason": f"{email} is invalid. {ERROR_MESSAGES.NOT_BUSINESS_EMAIL}"})
                continue

            # Check if user already exists
            existing_user = Users.get_user_by_email(email)

            if existing_user and not existing_user.company_id == NEW_INDICATOR and not existing_user.company_id == user.company_id:
                validation_errors.append({"reason": f"{email} is already associated with another company."})
                
        # If any validation errors, throw exception with details
        if validation_errors:
            error_details = [f"{item['reason']}" for item in validation_errors]
            error_message = "No users were invited. The following emails have issues:\n" + ", ".join(error_details)
            
            raise HTTPException(
                status_code=400,
                detail=error_message
            )
        
        # Only create groups if all invitees can be invited
        groups = []
        
        # Create new groups
        for group_name in form_data.group_names or []:
            try:
                group = Groups.insert_new_group(user.company_id, GroupForm(name=group_name, description=""))
                groups.append(group)
            except Exception as e:
                log.error(f"Failed to create group {group_name}: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to create group {group_name}"
                )
        
        # Get existing groups
        for group_id in form_data.group_ids or []:
            try:
                group = Groups.get_group_by_id(group_id)
                if not group:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Group with ID {group_id} not found"
                    )
                groups.append(group)
            except Exception as e:
                log.error(f"Failed to get group with ID {group_id}: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to get group with ID {group_id}"
                )
                
        # Second pass: actually invite the users (all should succeed)
        successful_invites = []

        for invitee in form_data.invitees:
            email = invitee.email.lower()
            
            # Check if user already exists and is not fully registered
            existing_user = Users.get_user_by_email(email)

            if existing_user:
                # Generate invite token
                invite_token = hashlib.sha256(email.encode()).hexdigest()
                
                # Send welcome email
                email_service = EmailService()
                email_service.send_invite_mail(
                    to_email=email,
                    invite_token=invite_token,
                    admin_name=user.first_name,
                    company_name=company.name
                )
                
                # Update existing user with invite information
                updated_user = Users.update_user_by_id(
                    existing_user.id,
                    {
                        "first_name": INVITED_INDICATOR,
                        "last_name": INVITED_INDICATOR,
                        "role": invitee.role,
                        "registration_code": None,
                        "company_id": user.company_id,
                        "invite_token": invite_token
                    }
                )
                
                # Add user to groups
                for group in groups:
                    if updated_user.id not in group.user_ids:
                        group.user_ids.append(updated_user.id)
                        Groups.update_group_by_id(group.id, group)
                
                successful_invites.append(email)
            else:
                # Generate invite token
                invite_token = hashlib.sha256(email.encode()).hexdigest()
                
                # Send welcome email
                email_service = EmailService()
                email_service.send_invite_mail(
                    to_email=email,
                    invite_token=invite_token,
                    admin_name=user.first_name,
                    company_name=company.name
                )
                
                # Create new user
                new_user = Users.insert_new_user(
                    str(uuid.uuid4()), 
                    INVITED_INDICATOR,
                    INVITED_INDICATOR,
                    email, 
                    user.company_id,
                    role=invitee.role,
                    invite_token=invite_token
                )
                
                # Add user to groups
                for group in groups:
                    if new_user.id not in group.user_ids:
                        group.user_ids.append(new_user.id)
                        Groups.update_group_by_id(group.id, group)
                
                successful_invites.append(email)
        
        # All invitations were successful
        return {"success": True, "message": "All users invited successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"An error occurred: {str(e)}"
        )


############################
# Create
############################


# Used to create a user at signup that will get linked to a company later in the registration process
@router.post("/create")
async def create_user(form_data: UserCreateForm):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if not is_business_email(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.NOT_BUSINESS_EMAIL
        )

    user = Users.get_user_by_email(form_data.email.lower())

    # Check if user exists and already linked to a company
    if user and not user.company_id == NEW_INDICATOR:
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    registration_code = str(random.randint(10 ** 8, 10 ** 9 - 1))

    if user:
        Users.update_user_by_id(user.id, {
            "first_name": NEW_INDICATOR,
            "last_name": NEW_INDICATOR,
            "registration_code": registration_code
        })
    else:
        user = Users.insert_new_user(str(uuid.uuid4()), NEW_INDICATOR, NEW_INDICATOR, form_data.email.lower(), NEW_INDICATOR, role="admin", registration_code=registration_code)

    # Send welcome email with the generated password
    email_service = EmailService()
    email_service.send_registration_mail(
        to_email=user.email,
        registration_code=registration_code
    )

    return user

############################
# GetUsers
############################


@router.get("/", response_model=list[UserModel])
async def get_users(
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    user=Depends(get_admin_user),
):
    return Users.get_users_by_company_id(user.company_id, skip, limit)


############################
# User Default Permissions

############################
class WorkspacePermissions(BaseModel):
    view_assistants: bool
    edit_assistants: bool
    view_knowledge: bool
    edit_knowledge: bool
    tools: bool
    view_prompts: bool
    edit_prompts: bool


class FeaturesPermissions(BaseModel):
    web_search: bool
    image_generation: bool
    code_interpreter: bool


class UserPermissions(BaseModel):
    workspace: WorkspacePermissions
    features: FeaturesPermissions


@router.get("/permissions", response_model=UserPermissions)
async def get_user_permissions(user=Depends(get_admin_user)):
    return {
        "workspace": WorkspacePermissions(
            **DEFAULT_USER_PERMISSIONS.get("workspace", {})
        ),
        "features": FeaturesPermissions(
            **DEFAULT_USER_PERMISSIONS.get("features", {})
        ),
    }


############################
# UpdateUserRole
############################


@router.post("/update/role", response_model=Optional[UserModel])
async def update_user_role(form_data: UserRoleUpdateForm, user=Depends(get_admin_user)):
    # Prevent updating the first user (super admin) - they should be protected
    if user.id == form_data.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An admin can't update his own role.",
        )

    # Get the target user
    user_obj = Users.get_user_by_id(form_data.id)

    if user_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Update CRM if needed
    try:
        loops_service.create_or_update_loops_contact(user)
        crm_service.update_user_access_level(user_email=user_obj.email, access_level=form_data.role)
    except Exception as e:
        log.error(f"Failed to update user access level in CRM or in Loops: {e}")

    # Update the user role
    return Users.update_user_role_by_id(form_data.id, form_data.role)


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        settings = user.settings or UserSettings()
        ui = settings.ui if isinstance(settings.ui, dict) else {}
        if not isinstance(ui.get("system"), dict):
            ui["system"] = {"promptStyle": "default"}
            settings.ui = ui
        return settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserSettingsBySessionUser
############################


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    form_data: UserSettings, user=Depends(get_verified_user)
):
    user = Users.update_user_by_id(user.id, {"settings": form_data.model_dump()})
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserInfoBySessionUser
############################


@router.get("/user/info", response_model=Optional[dict])
async def get_user_info_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.info
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserInfoBySessionUser
############################


@router.post("/user/info/update", response_model=Optional[dict])
async def update_user_info_by_session_user(
    form_data: dict, user=Depends(get_verified_user)
):
    user = Users.get_user_by_id(user.id)
    if user:
        if user.info is None:
            user.info = {}

        user = Users.update_user_by_id(user.id, {"info": {**user.info, **form_data}})
        if user:
            return user.info
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserById
############################


class UserResponse(BaseModel):
    first_name: str
    last_name: str
    profile_image_url: str
    active: Optional[bool] = None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, user=Depends(get_verified_user)):
    # Check if user_id is a shared chat
    # If it is, get the user_id from the chat
    if user_id.startswith("shared-"):
        chat_id = user_id.replace("shared-", "")
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            user_id = chat.user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )

    user = Users.get_user_by_id(user_id)

    if user:
        return UserResponse(
            **{
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_image_url": user.profile_image_url,
                "active": get_active_status_by_user_id(user_id),
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserById
############################


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
):
    user = Users.get_user_by_id(user_id)

    if user:
        if form_data.email.lower() != user.email:
            email_user = Users.get_user_by_email(form_data.email.lower())
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.EMAIL_TAKEN,
                )

        if form_data.password:
            hashed = get_password_hash(form_data.password)
            log.debug(f"hashed: {hashed}")
            Auths.update_user_password_by_id(user_id, hashed)

        Auths.update_email_by_id(user_id, form_data.email.lower())
        updated_user = Users.update_user_by_id(
            user_id,
            {
                "name": form_data.name,
                "email": form_data.email.lower(),
                "profile_image_url": form_data.profile_image_url,
            },
        )

        if updated_user:
            loops_service.create_or_update_loops_contact(user)
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# GetUserEntities
############################


class EntityItem(BaseModel):
    id: str
    name: str


class UserEntitiesResponse(BaseModel):
    models: list[EntityItem]
    prompts: list[EntityItem]
    knowledge: list[EntityItem]


class TransferItem(BaseModel):
    entity_type: str  # "model" | "prompt" | "knowledge"
    entity_id: str
    new_user_id: str


class TransferEntitiesForm(BaseModel):
    assignments: list[TransferItem]


@router.get("/{user_id}/entities", response_model=UserEntitiesResponse)
async def get_user_entities(user_id: str, user=Depends(get_verified_user)):
    target_user = Users.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.USER_NOT_FOUND)

    if user.id != user_id:
        if user.role != "admin" or target_user.company_id != user.company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    company_id = target_user.company_id

    models = [EntityItem(id=m.id, name=m.name) for m in Models.get_models_owned_by_user(user_id, company_id)]
    prompts = [EntityItem(id=p.command, name=p.title) for p in Prompts.get_prompts_owned_by_user(user_id, company_id)]
    knowledge = [EntityItem(id=k.id, name=k.name) for k in Knowledges.get_knowledge_owned_by_user(user_id, company_id)]

    return UserEntitiesResponse(models=models, prompts=prompts, knowledge=knowledge)


@router.post("/{user_id}/transfer-entities", response_model=bool)
async def transfer_user_entities(user_id: str, form_data: TransferEntitiesForm, user=Depends(get_verified_user)):
    target_user = Users.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.USER_NOT_FOUND)

    if user.id != user_id:
        if user.role != "admin" or target_user.company_id != user.company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACTION_PROHIBITED)

    company_id = target_user.company_id

    model_assignments: dict[str, list[str]] = {}
    prompt_assignments: dict[str, list[str]] = {}
    knowledge_assignments: dict[str, list[str]] = {}

    for assignment in form_data.assignments:
        if assignment.entity_type == "model":
            model_assignments.setdefault(assignment.new_user_id, []).append(assignment.entity_id)
        elif assignment.entity_type == "prompt":
            prompt_assignments.setdefault(assignment.new_user_id, []).append(assignment.entity_id)
        elif assignment.entity_type == "knowledge":
            knowledge_assignments.setdefault(assignment.new_user_id, []).append(assignment.entity_id)

    for new_user_id, ids in model_assignments.items():
        Models.transfer_models_to_user(ids, new_user_id, company_id)

    for new_user_id, commands in prompt_assignments.items():
        Prompts.transfer_prompts_to_user(commands, new_user_id, company_id)

    for new_user_id, ids in knowledge_assignments.items():
        Knowledges.transfer_knowledge_to_user(ids, new_user_id, company_id)

    return True


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_verified_user)):
    target_user = Users.get_user_by_id(user_id)

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )

    # A regular user may only delete themselves.
    # An admin may delete any user within the same company.
    if user.id != user_id:
        if user.role != "admin" or target_user.company_id != user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACTION_PROHIBITED,
            )

    company_id = target_user.company_id

    # Always fetch files before deletion for storage cleanup
    user_files = Files.get_files_by_user_id(user_id)

    def _cleanup_files():
        for file in user_files:
            collection_name = f"file-{file.id}"

            try:
                if VECTOR_DB_CLIENT.has_collection(collection_name=collection_name):
                    VECTOR_DB_CLIENT.delete_collection(collection_name=collection_name)
            except Exception as e:
                log.warning(f"Failed to delete vector collection {collection_name}: {e}")

            try:
                Storage.delete_file(file.path)
            except Exception as e:
                log.warning(f"Failed to delete file {file.path} from storage: {e}")

    def _clear_company_caches():
        for cache, name in (
            (STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE, "STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE"),
            (STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE, "STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE"),
            (COMPANY_CONFIG_CACHE, "COMPANY_CONFIG_CACHE"),
        ):
            try:
                if company_id in cache:
                    del cache[company_id]
            except Exception as e:
                log.warning(f"Failed to clear {name} for company {company_id}: {e}")

    # ------------------------------------------------------------------
    # Last-user check: if this is the only user left in the company,
    # cancel the Stripe subscription and delete the entire company
    # (PG cascades handle user + all dependent rows).
    # ------------------------------------------------------------------
    total_users = Users.count_users_by_company_id(company_id)

    if total_users == 1:
        _cleanup_files()
        payments_service.cancel_company_subscription(company_id)
        _clear_company_caches()

        if not Companies.delete_company_by_id(company_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ERROR_MESSAGES.DELETE_USER_ERROR,
            )

        return True

    # ------------------------------------------------------------------
    # Last-admin check: if this is the only admin left, promote a random
    # non-pending user. If ALL remaining users are pending there is nobody
    # to promote — treat it as "last active user" and delete the company.
    # ------------------------------------------------------------------
    if target_user.role == "admin":
        admin_users = Users.get_admin_users_by_company(company_id)
        if len(admin_users) == 1:
            all_company_users = Users.get_users_by_company_id(company_id)
            candidate = next(
                (
                    u for u in all_company_users
                    if u.id != user_id
                    and u.invite_token is None
                    and u.registration_code is None
                ),
                None,
            )
            if candidate:
                Users.update_user_role_by_id(candidate.id, "admin")
                log.info(
                    f"Promoted user {candidate.id} to admin after last admin "
                    f"{user_id} was deleted in company {company_id}"
                )
            else:
                # Only pending invites remain — no one can ever log in.
                # Delete the company (cascades through everything).
                _cleanup_files()
                payments_service.cancel_company_subscription(company_id)
                _clear_company_caches()
                if not Companies.delete_company_by_id(company_id):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=ERROR_MESSAGES.DELETE_USER_ERROR,
                    )
                return True

    success = Users.delete_user_by_id(user_id)

    if success:
        _cleanup_files()
        payments_service.update_premium_seat_count(company_id)
        return True

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ERROR_MESSAGES.DELETE_USER_ERROR,
    )


############################
# ReinviteUser
############################


@router.post("/reinvite")
async def reinvite_user(form_data: UserReinviteForm, user=Depends(get_admin_user)):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if not is_business_email(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.NOT_BUSINESS_EMAIL
        )

    existing_user = Users.get_user_by_email(form_data.email.lower())

    if not existing_user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.USER_NOT_FOUND
        )

    # Generate a new invite token
    invite_token = hashlib.sha256(form_data.email.lower().encode()).hexdigest()

    # Update the user with the new invite token
    updated_user = Users.update_user_by_id(existing_user.id, {"invite_token": invite_token})

    if not updated_user:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user"
        )

    company = Companies.get_company_by_id(user.company_id)

    # Send the invitation email
    email_service = EmailService()
    email_service.send_invite_mail(
        to_email=form_data.email.lower(),
        invite_token=invite_token,
        admin_name=user.first_name,
        company_name=company.name
    )

    return {"message": "User reinvited successfully", "user_id": existing_user.id}


############################
# RevokeInvite
############################


@router.post("/revoke-invite")
async def revoke_user_invite(form_data: UserRevokeInviteForm, user=Depends(get_admin_user)):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    existing_user = Users.get_user_by_email(form_data.email.lower())
    if not existing_user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.USER_NOT_FOUND
        )

    # Check if the user has an invite token
    if not existing_user.invite_token:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="User does not have an active invitation"
        )

    # Delete the user from the database
    success = Users.delete_user_by_email(form_data.email.lower())
    if not success:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user"
        )

    return {"message": "User invitation revoked and user deleted successfully", "user_id": existing_user.id}
