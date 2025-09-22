import hashlib
import logging
import random
import uuid
from typing import Optional

from beyond_the_loop.models.users import UserInviteForm, UserCreateForm
from beyond_the_loop.models.auths import Auths
from beyond_the_loop.models.groups import Groups, GroupForm
from beyond_the_loop.models.companies import Companies
from beyond_the_loop.models.chats import Chats
from beyond_the_loop.models.users import (
    UserModel,
    UserRoleUpdateForm,
    Users,
    UserSettings,
    UserUpdateForm,
    UserReinviteForm,
    UserRevokeInviteForm
)


from open_webui.socket.main import get_active_status_by_user_id
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from open_webui.utils.auth import get_admin_user, get_password_hash, get_verified_user
from open_webui.utils.misc import validate_email_format
from beyond_the_loop.services.email_service import EmailService
from beyond_the_loop.utils.access_control import DEFAULT_USER_PERMISSIONS
from beyond_the_loop.services.crm_service import crm_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


@router.post("/invite")
async def invite_user(form_data: UserInviteForm, user=Depends(get_admin_user)):
    validation_errors = []
    
    try:
        # Get the active subscription to check seat limits
        from beyond_the_loop.routers.payments import get_subscription
        from beyond_the_loop.models.users import Users

        company = Companies.get_company_by_id(user.company_id)

        if not company.subscription_not_required:
            # Get subscription details
            subscription_details = await get_subscription(user)

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

            # Check if user already exists
            existing_user = Users.get_user_by_email(email)
            if existing_user and not existing_user.registration_code:
                validation_errors.append({"reason": f"{email} is already taken"})
                
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
            if existing_user and existing_user.registration_code:
                # Generate invite token
                invite_token = hashlib.sha256(email.encode()).hexdigest()
                
                # Send welcome email
                email_service = EmailService()
                email_service.send_invite_mail(
                    to_email=email,
                    invite_token=invite_token
                )
                
                # Update existing user with invite information
                updated_user = Users.update_user_by_id(
                    existing_user.id,
                    {
                        "first_name": "INVITED",
                        "last_name": "INVITED",
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
                    invite_token=invite_token
                )
                
                # Create new user
                new_user = Users.insert_new_user(
                    str(uuid.uuid4()), 
                    "INVITED", 
                    "INVITED", 
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
            
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"An error occurred: {str(e)}"
        )


############################
# Create
############################


@router.post("/create")
async def create_user(form_data: UserCreateForm):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    user = Users.get_user_by_email(form_data.email.lower())

    if user and not user.registration_code:
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    if not user:
        registration_code = str(random.randint(10**8, 10**9 - 1))
        user = Users.insert_new_user(str(uuid.uuid4()), "NEW", "NEW", form_data.email.lower(), "NEW", role="admin", registration_code=registration_code)
    else:
        registration_code = user.registration_code

    # Send welcome email with the generated password
    email_service = EmailService()
    email_service.send_registration_email(
        to_email=user.email,
        registration_code=registration_code,
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
    knowledge: bool
    tools: bool
    view_prompts: bool
    edit_prompts: bool

class ChatPermissions(BaseModel):
    controls: bool
    file_upload: bool
    delete: bool
    edit: bool
    temporary: bool


class FeaturesPermissions(BaseModel):
    web_search: bool
    image_generation: bool
    code_interpreter: bool


class UserPermissions(BaseModel):
    workspace: WorkspacePermissions
    chat: ChatPermissions
    features: FeaturesPermissions


@router.get("/permissions", response_model=UserPermissions)
async def get_user_permissions(request: Request, user=Depends(get_admin_user)):
    return {
        "workspace": WorkspacePermissions(
            **DEFAULT_USER_PERMISSIONS.get("workspace", {})
        ),
        "chat": ChatPermissions(
            **DEFAULT_USER_PERMISSIONS.get("chat", {})
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
    if user.id != form_data.id and form_data.id != Users.get_first_user().id:
        user_obj = Users.get_user_by_id(form_data.id)
        if user_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        try:
            crm_service.update_user_access_level(user_email=user_obj.email, access_level=form_data.role)
        except Exception as e:
            log.error(f"Failed to update user access level in CRM: {e}")

        return Users.update_user_role_by_id(form_data.id, form_data.role)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
    )


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
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
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    if user.id != user_id:
        result = Auths.delete_auth_by_id(user_id)

        if result:
            return True

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DELETE_USER_ERROR,
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
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

    # Send the invitation email
    email_service = EmailService()
    email_sent = email_service.send_invite_mail(
        to_email=form_data.email.lower(),
        invite_token=invite_token
    )

    if not email_sent:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send invitation email"
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
