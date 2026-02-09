from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy import String, Column, BigInteger, Text, ForeignKey, Float

import uuid
import time

from open_webui.internal.db import get_db, Base

####################
# Completion DB Schema
####################

class Completion(Base):
    __tablename__ = "completion"

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    model = Column(Text)
    credits_used = Column(Float)
    created_at = Column(BigInteger)
    assistant = Column(Text)

class CompletionModel(BaseModel):
    id: str
    user_id: str
    model: str
    credits_used: float
    created_at: int  # timestamp in epoch
    assistant: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CompletionTable:
    def insert_new_completion(self, user_id: str, model: str, credits_used: float, assistant: str) -> Optional[CompletionModel]:
        completion = CompletionModel(
            **{
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "created_at": int(time.time()),
                "model": model,
                "credits_used": credits_used,
                "assistant": assistant
            }
        )

        try:
            with get_db() as db:
                result = Completion(**completion.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return CompletionModel.model_validate(result)
                else:
                    print("insertion failed", result)
                    return None
        except Exception as e:
            print(f"Error creating completion: {e}")
            return None

    def get_completions_last_three_hours_by_user_and_model(
            self,
            user_id: str,
            model_name: str
    ) -> int:
        try:
            now = int(time.time())
            three_hours_ago = now - (3 * 60 * 60)

            with get_db() as db:
                count = (
                    db.query(Completion)
                    .filter(
                        Completion.user_id == user_id,
                        Completion.model == model_name,
                        Completion.created_at >= three_hours_ago,
                    )
                    .count()
                )

                return count
        except Exception as e:
            print(f"Error fetching completions for usage count: {e}")
            return 0


Completions = CompletionTable()
