import logging
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_db
from beyond_the_loop.models.users import UserModel, Users
from beyond_the_loop.models.companies import Companies
from open_webui.env import SRC_LOG_LEVELS
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, String, Text
from open_webui.utils.auth import verify_password
from beyond_the_loop.services.crm_service import crm_service
from beyond_the_loop.services.loops_service import loops_service
from beyond_the_loop.routers.payments import get_subscription
import stripe

from beyond_the_loop.services.payments_service import payments_service

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# DB MODEL
####################


class Auth(Base):
    __tablename__ = "auth"

    id = Column(String, primary_key=True)
    email = Column(String)
    password = Column(Text)
    active = Column(Boolean)


class AuthModel(BaseModel):
    id: str
    email: str
    password: str
    active: bool = True


####################
# Forms
####################


class Token(BaseModel):
    token: str
    token_type: str


class ApiKey(BaseModel):
    api_key: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    profile_image_url: str


class SigninResponse(Token, UserResponse):
    pass


class SigninForm(BaseModel):
    email: str
    password: str


class LdapForm(BaseModel):
    user: str
    password: str


class ProfileImageUrlForm(BaseModel):
    profile_image_url: str


class UpdateProfileForm(BaseModel):
    profile_image_url: str
    first_name: str
    last_name: str
    password: Optional[str] = None


class UpdatePasswordForm(BaseModel):
    password: str
    new_password: str

class ResetPasswordRequestForm(BaseModel):
    email: str

class ResetPasswordForm(BaseModel):
    reset_token: str
    new_password: str

class SignupForm(BaseModel):
    first_name: str
    last_name: str
    password: str
    signup_token: str
    profile_image_url: Optional[str] = "/user.png"
    is_invited: bool = False

class AuthsTable:
    def insert_new_auth(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        company_id: str,
        profile_image_url: str = "/user.png",
        role: str = "pending",
        oauth_sub: Optional[str] = None,
    ) -> Optional[UserModel]:
        with get_db() as db:
            log.info("insert_new_auth")

            id = str(uuid.uuid4())

            auth = AuthModel(
                **{"id": id, "email": email, "password": password, "active": True}
            )
            result = Auth(**auth.model_dump())
            db.add(result)

            user = Users.insert_new_user(
                id, first_name, last_name, email, company_id, profile_image_url, role, oauth_sub
            )

            db.commit()
            db.refresh(result)

            if company_id not in ["NEW", "NO_COMPANY"]:
                subscription = payments_service.get_subscription(user.company_id)

                try:
                    if subscription.get("plan") == "premium":
                        stripe.Subscription.modify(
                            subscription.get("subscription_id"),
                            items=[{
                                "id": subscription.get("subscription_item_id"),
                                "quantity": Users.get_num_active_users_by_company_id(user.company_id)
                            }],
                            proration_behavior="none"  # disables proration
                        )
                except Exception as e:
                    log.error(f"Failed to update subscription on signup (insert new auth): {e}")

                try:
                        loops_service.create_or_update_loops_contact(user)
                        company = Companies.get_company_by_id(company_id).name
                        crm_service.create_user(company_name=company.name, user_email=user.email, user_firstname=user.first_name, user_lastname=user.last_name, access_level=user.role)
                except Exception as e:
                    log.error(f"Failed to create user in CRM or in Loops: {e}")

            if result and user:
                return user
            else:
                return None

    def insert_auth_for_existing_user(self, user: UserModel, password: str):
        with get_db() as db:
            auth = AuthModel(
                **{"id": user.id, "email": user.email, "password": password, "active": True}
            )
            result = Auth(**auth.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)

            if user.company_id != "NEW":
                company = Companies.get_company_by_id(user.company_id).name

                subscription = payments_service.get_subscription(user.company_id)

                try:
                    if subscription.get("plan") == "premium":
                        stripe.Subscription.modify(
                            subscription.get("subscription_id"),
                            items=[{
                                "id": subscription.get("subscription_item_id"),
                                "quantity": Users.get_num_active_users_by_company_id(user.company_id)
                            }],
                            proration_behavior="none"  # disables proration
                        )
                except Exception as e:
                    log.error(f"Failed to update subscription on signup (insert new auth for existing user): {e}")

                try:
                    loops_service.create_or_update_loops_contact(user)
                    crm_service.create_user(company_name=company, user_email=user.email, user_firstname=user.first_name, user_lastname=user.last_name, access_level=user.role)
                except Exception as e:
                    log.error(f"Failed to create user in CRM or in Loops: {e}")

            if result:
                return True
            else:
                return False

    def authenticate_user(self, email: str, password: str) -> Optional[UserModel]:
        log.info(f"authenticate_user: {email}")
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if auth:
                    if verify_password(password, auth.password):
                        user = Users.get_user_by_id(auth.id)
                        return user
                    else:
                        return None
                else:
                    return None
        except Exception:
            return None

    def authenticate_user_by_trusted_header(self, email: str) -> Optional[UserModel]:
        log.info(f"authenticate_user_by_trusted_header: {email}")
        try:
            with get_db() as db:
                auth = db.query(Auth).filter_by(email=email, active=True).first()
                if auth:
                    user = Users.get_user_by_id(auth.id)
                    return user
        except Exception:
            return None

    def update_user_password_by_id(self, id: str, new_password: str) -> bool:
        try:
            with get_db() as db:
                result = (
                    db.query(Auth).filter_by(id=id).update({"password": new_password})
                )
                db.commit()
                return True if result == 1 else False
        except Exception:
            return False

    def update_email_by_id(self, id: str, email: str) -> bool:
        try:
            with get_db() as db:
                result = db.query(Auth).filter_by(id=id).update({"email": email})
                db.commit()
                return True if result == 1 else False
        except Exception:
            return False

    def delete_auth_by_id(self, id: str, company_id: str) -> bool:
        try:
            with get_db() as db:
                # Delete User
                result = Users.delete_user_by_id(id)

                if result:
                    db.query(Auth).filter_by(id=id).delete()
                    db.commit()

                    subscription = payments_service.get_subscription(company_id)

                    try:
                        if subscription.get("plan") == "premium":
                            stripe.Subscription.modify(
                                subscription.get("subscription_id"),
                                items=[{
                                    "id": subscription.get("subscription_item_id"),
                                    "quantity": Users.get_num_active_users_by_company_id(company_id)
                                }],
                                proration_behavior="none"  # disables proration
                            )
                    except Exception as e:
                        log.error(f"Failed to update subscription on signup (insert new auth): {e}")

                    return True
                else:
                    return False
        except Exception:
            return False


Auths = AuthsTable()
