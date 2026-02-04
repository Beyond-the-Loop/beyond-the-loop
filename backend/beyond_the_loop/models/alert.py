from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Enum
import enum
from typing import Optional

from open_webui.internal.db import get_db
from open_webui.internal.db import Base

class AlertType(enum.Enum):
    info = "info"
    warning = "warning"
    success = "success"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(Enum(AlertType, name="alert_type", create_type=False), nullable=False)

class AlertModel(BaseModel):
    title: str
    message: str
    type: Optional[AlertType]

class AlertTable:
    def get_alert(self):
        with get_db() as db:
            return db.query(Alert).first()

Alerts = AlertTable()
