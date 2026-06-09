import logging
import time
from typing import Optional

from open_webui.internal.db import Base, JSONField, get_db
from open_webui.env import SRC_LOG_LEVELS

from beyond_the_loop.config import LITELLM_MODEL_CONFIG
from beyond_the_loop.models.users import UserResponse, Users
from beyond_the_loop.models.prompts import Prompt
from beyond_the_loop.models.files import Files

from pydantic import BaseModel, ConfigDict

from sqlalchemy import BigInteger, Column, Text, JSON, Boolean, Table, ForeignKey, or_, String
from sqlalchemy.orm import relationship
from sqlalchemy import select, delete, insert
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

from beyond_the_loop.models.groups import Groups
from beyond_the_loop.utils.access_control import has_access


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

user_model_bookmark = Table(
    "user_model_bookmark",
    Base.metadata,
    Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("model_id", ForeignKey("model.id", ondelete="CASCADE"), primary_key=True),
)


####################
# Models DB Schema
####################


# ModelParams is a model for the data stored in the params field of the Model table
class ModelParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    pass


# ModelMeta is a model for the data stored in the meta field of the Model table
class ModelMeta(BaseModel):
    profile_image_url: Optional[str] = "/static/favicon.png"

    description: Optional[str] = None
    """
        User-facing description of the model.
    """

    tags: Optional[list[dict]] = None

    model_config = ConfigDict(extra="allow")

    files: Optional[list[dict]] = None

    knowledge: Optional[list[dict]] = None

    is_kickstart_assistant: Optional[bool] = None

    pass


class Model(Base):
    __tablename__ = "model"

    id = Column(Text, primary_key=True)
    """
        The model's id as used in the API. If set to an existing model, it will override the model.
    """

    base_model_id = Column(Text, nullable=True)
    """
        An optional pointer to the actual model that should be used when proxying requests.
    """

    name = Column(Text, nullable=False)
    """
        The human-readable display name of the model.
    """

    params = Column(JSONField)
    """
        Holds a JSON encoded blob of parameters, see `ModelParams`.
    """

    meta = Column(JSONField)
    """
        Holds a JSON encoded blob of metadata, see `ModelMeta`.
    """

    user_id = Column(Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    company_id = Column(Text, nullable=False)

    access_control = Column(JSON, nullable=True)  # Controls data access levels.
    # Defines access control rules for this entry.
    # - `None`: Public access, available to all users with the "user" role.
    # - `{}`: Private access, restricted exclusively to the owner.
    # - Custom permissions: Specific access control for reading and writing;
    #   Can specify group or user-level restrictions:
    #   {
    #      "read": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      },
    #      "write": {
    #          "group_ids": ["group_id1", "group_id2"],
    #          "user_ids":  ["user_id1", "user_id2"]
    #      }
    #   }

    is_active = Column(Boolean, nullable=False, default=True)

    updated_at = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)

    bookmarking_users = relationship(
        "User",
        secondary="user_model_bookmark",
        back_populates="model_bookmarks"
    )


class ModelModel(BaseModel):
    id: str
    base_model_id: Optional[str] = None

    name: str
    params: Optional[ModelParams] = None
    meta: ModelMeta

    access_control: Optional[dict] = None

    is_active: bool
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch

    user_id: Optional[str]
    company_id: str

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################

class ModelResponse(ModelModel):
    fair_usage_limit_reached: Optional[bool] = None

class ModelUserResponse(ModelModel):
    user: Optional[UserResponse] = None
    bookmarked_by_user: Optional[bool] = False


class ModelForm(BaseModel):
    id: str
    base_model_id: Optional[str] = None
    name: str
    meta: ModelMeta
    params: ModelParams
    access_control: Optional[dict] = None
    is_active: bool = True
    updated_at: int = int(time.time())

class TagResponse(BaseModel):
    name: str
    is_system: bool 

class ModelsTable:
    def insert_new_model(
        self, form_data: ModelForm, user_id: str, company_id: str
    ) -> Optional[ModelModel]:

        model = ModelModel(
            **{
                **form_data.model_dump(),
                "company_id": company_id,
                "user_id": user_id,
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
            }
        )
        try:
            with get_db() as db:
                result = Model(**model.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)

                if result:
                    return ModelModel.model_validate(result)
                else:
                    return None
        except Exception as e:
            log.error(f"Error inserting model: {e}")
            return None

    def get_all_models_by_company(self, company_id: str) -> list[ModelModel]:
        with get_db() as db:
            return [ModelModel.model_validate(model) for model in db.query(Model).filter(Model.company_id == company_id).all()]

    def get_base_models_by_comany_and_user(self, company_id: str, user_id: str, role: str) -> list[ModelModel]:
        with get_db() as db:
            models = db.query(Model).filter(Model.base_model_id == None, Model.company_id == company_id).all()

        user_groups = Groups.get_groups_by_member_id(user_id)
        return [
            ModelModel.model_validate(model)
            for model in models
            if has_access(user_id, user_groups, "read", model.access_control) or role == "admin"
        ]

    def get_active_base_models_by_company_and_user(self, company_id: str, user_id: str, role: str) -> list[ModelModel]:
        with get_db() as db:
            models = db.query(Model).filter(Model.base_model_id == None, Model.company_id == company_id, Model.is_active).all()
        user_groups = Groups.get_groups_by_member_id(user_id)
        return [
            ModelModel.model_validate(model)
            for model in models
            if has_access(user_id, user_groups, "read", model.access_control) or role == "admin"
        ]

    def get_assistants_by_user_and_company(
        self, user_id: str, company_id: str, permission: str = "read", is_kickstart_customer = False
    ) -> list[ModelUserResponse]:
        with get_db() as db:
            result = db.execute(
                select(user_model_bookmark.c.model_id).where(user_model_bookmark.c.user_id == user_id)
            )
            bookmarked_model_ids = {row.model_id for row in result.fetchall()}

        
        models = self.get_all_models_by_company(company_id)
        assistants = [model for model in models if model.base_model_id]


        # Batch-fetch all users in one query instead of N+1 individual queries
        user_ids = list({m.user_id for m in assistants if m.user_id != "system"})
        users_map = {u.id: u for u in Users.get_users_by_user_ids(user_ids)} if user_ids else {}

        models_user_responses = []
        for assistant in assistants:
            user = users_map.get(assistant.user_id) if assistant.user_id != "system" else None
            models_user_responses.append(
                ModelUserResponse.model_validate(
                    {
                        **ModelModel.model_validate(assistant).model_dump(),
                        "user": user.model_dump() if user else None,
                    }
                )
            )

        user_groups = Groups.get_groups_by_member_id(user_id)
        filtered_assistants = []

        allowed_kickstart_models = {
            "Scout, der KI-Einsatz-Berater",
            "Leo, der Lektor",
            "Tom, der Rechercheassistent"
        }

        for assistant in assistants:
            if (
                assistant.user_id == user_id
                or has_access(user_id, user_groups, permission, assistant.access_control)
                    and (assistant.meta.is_kickstart_assistant is None or is_kickstart_customer or assistant.name in allowed_kickstart_models)
            ):
                # Resolve system model base_model_id from name to actual ID using the pre-fetched map
                if assistant.user_id == "system":
                    resolved_id = {m.name: m.id for m in models}.get(assistant.base_model_id)
                    if resolved_id:
                        assistant.base_model_id = resolved_id

                model_dict = assistant.model_dump()
                model_dict["bookmarked_by_user"] = assistant.id in bookmarked_model_ids
                filtered_assistants.append(ModelUserResponse(**model_dict))

        filtered_assistants.sort(
            key=lambda m: (m.bookmarked_by_user, m.created_at),
            reverse=True
        )

        return filtered_assistants

    def get_assistants_lite_by_user_and_company(
        self, user_id: str, company_id: str, permission: str = "read", is_kickstart_customer = False
    ) -> list[ModelUserResponse]:
        """Returns assistants for list views — strips heavy params and meta.knowledge/files fields."""
        assistants = self.get_assistants_by_user_and_company(user_id, company_id, permission, is_kickstart_customer=is_kickstart_customer)
        for model in assistants:
            model.params = None
            if model.meta:
                model.meta.knowledge = None
                model.meta.files = None
        return assistants

    def get_model_by_id(self, id: str) -> Optional[ModelModel]:
        try:
            with get_db() as db:
                model = db.query(Model).filter_by(id=id).first()
                return ModelModel.model_validate(model)
        except Exception:
            return None

    def get_model_by_name_and_company(self, name: str, company_id: str) -> Optional[ModelModel]:
        try:
            with get_db() as db:
                model = db.query(Model).filter_by(name=name, company_id=company_id).first()
                return ModelModel.model_validate(model)
        except Exception:
            return None

    def toggle_model_by_id_and_company(self, id: str, company_id: str) -> Optional[ModelModel]:
        with get_db() as db:
            try:
                is_active = db.query(Model).filter_by(id=id, company_id=company_id).first().is_active

                db.query(Model).filter_by(id=id, company_id=company_id).update(
                    {
                        "is_active": not is_active,
                        "updated_at": int(time.time()),
                    }
                )
                db.commit()

                return self.get_model_by_id(id)
            except Exception:
                return None

    def update_model_by_id_and_company(self, id: str, model: ModelForm, company_id: str) -> Optional[ModelModel]:
        try:
            model.updated_at = int(time.time())

            with get_db() as db:
                # update only the fields that are present in the model
                (
                    db.query(Model)
                    .filter_by(id=id, company_id=company_id)
                    .update(model.model_dump(exclude={"id"}))
                )
                db.commit()

                model = db.get(Model, id)
                db.refresh(model)
                return ModelModel.model_validate(model)
        except Exception as e:
            log.error(f"Error updating model: {e}")
            return None


    def delete_model_by_id_and_company(self, id: str, company_id: str) -> bool:
        try:
            with get_db() as db:
                db.query(Model).filter_by(id=id, company_id=company_id).delete()
                db.commit()

                return True
        except Exception:
            return False
        
    def toggle_bookmark(self, model_id: str, user_id: str) -> bool:
        # Check if bookmark exists
        try:
            with get_db() as db:
                exists = db.execute(
                    select(user_model_bookmark).where(
                        (user_model_bookmark.c.user_id == user_id) &
                        (user_model_bookmark.c.model_id == model_id)
                    )
                ).fetchone()

                if exists:
                    db.execute(
                        delete(user_model_bookmark).where(
                            (user_model_bookmark.c.user_id == user_id) &
                            (user_model_bookmark.c.model_id == model_id)
                        )
                    )
                    db.commit()
                    return False  # Bookmark was removed
                else:
                    db.execute(
                        insert(user_model_bookmark).values(
                            user_id=user_id,
                            model_id=model_id
                        )
                    )
                    db.commit()
                    return True
        
        except Exception:
            return None
    
    def get_system_and_user_tags(self, user_id: str) -> list[TagResponse]:
        try:
            with get_db() as db:
                prompts = (
                    db.query(Prompt)
                    .filter(
                        Prompt.user_id == "system")
                    .all()
                )

                models = (
                    db.query(Model)
                    .filter(Model.user_id == user_id)
                    .all()
                )

                tag_map = {}

                for prompt in prompts:
                    meta = prompt.meta

                    tags = meta.get("tags", [])

                    for tag in tags:
                        name = tag.get("name")
                        if not name:
                            continue

                        if name not in tag_map:
                            tag_map[name] = {"name": name, "is_system": True}

                for model in models:
                    meta = model.meta
                    tags = meta.get("tags", [])
                    if tags is None:
                        tags = []

                    for tag in tags:
                        name = tag.get("name")
                        if not name:
                            continue
                        if name not in tag_map:
                            tag_map[name] = {"name": name, "is_system": False}
                return list(tag_map.values())
        except Exception as e:
            log.error(f"Error in get_system_and_user_tags: {e}")
            return []

    def get_models_by_knowledge_id(self, knowledge_id: str):
        with get_db() as db:
            return db.query(Model).filter(cast(Model.meta, JSONB)["knowledge"].contains([{"id": knowledge_id}])).all()

    def get_models_owned_by_user(self, user_id: str, company_id: str) -> list[ModelModel]:
        with get_db() as db:
            rows = db.query(Model).filter(
                Model.user_id == user_id,
                Model.company_id == company_id,
            ).all()
            return [ModelModel.model_validate(r) for r in rows]

    def transfer_models_to_user(self, model_ids: list[str], new_user_id: str, company_id: str) -> bool:
        if not model_ids:
            return True
        try:
            with get_db() as db:
                model_rows = db.query(Model).filter(
                    Model.id.in_(model_ids),
                    Model.company_id == company_id,
                ).all()

                file_ids = []
                for m in model_rows:
                    if m.meta and isinstance(m.meta, dict):
                        for f in (m.meta.get("files") or []):
                            if isinstance(f, dict) and f.get("id"):
                                file_ids.append(f["id"])

                db.query(Model).filter(
                    Model.id.in_(model_ids),
                    Model.company_id == company_id,
                ).update({"user_id": new_user_id}, synchronize_session=False)
                db.commit()

            if file_ids:
                Files.transfer_files_to_user(file_ids, new_user_id)

            return True
        except Exception as e:
            log.error(f"Error transferring models to user {new_user_id}: {e}")
            return False


Models = ModelsTable()


PERPLEXITY_ALLOWED_COMPANY_IDS = (
    "c57c8e55-67b5-4dc6-87cc-cbe3e4b201e4",
    "995d24a9-fc30-43b3-b88b-e8650586d938",
)
PERPLEXITY_MODELS = (
    "Perplexity Sonar Pro",
    "Perplexity Sonar Deep Research",
    "Perplexity Sonar Reasoning Pro",
)


def filter_base_models_by_plan(base_models, plan: str | None, company_id: str):
    # Why: mirrors the access logic in main.py:get_active_models so the public API
    # exposes the same set of base models that the regular chat path can call.
    if plan not in ("free", "premium"):
        return base_models

    allowed_premium = {
        name for name, cfg in LITELLM_MODEL_CONFIG.items()
        if cfg.get("allowed_messages_per_three_hours_premium")
    }
    base_models = [m for m in base_models if m.name in allowed_premium]

    if plan == "free":
        allowed_free = {
            name for name, cfg in LITELLM_MODEL_CONFIG.items()
            if cfg.get("allowed_messages_per_three_hours_free")
        }
        base_models = [m for m in base_models if m.name in allowed_free]

    if company_id not in PERPLEXITY_ALLOWED_COMPANY_IDS:
        base_models = [m for m in base_models if m.name not in PERPLEXITY_MODELS]

    return base_models
