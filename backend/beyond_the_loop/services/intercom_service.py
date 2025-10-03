import logging
import os
import jwt
from datetime import datetime, timedelta

from beyond_the_loop.models.users import User

log = logging.getLogger(__name__)


class IntercomService:
    def __init__(self):
        self.api_secret_key = os.getenv("INTERCOM_API_SECRET_KEY")

    def generate_user_token(self, user: User):
        try:
            expires_at = int((datetime.now() + timedelta(hours=3)).timestamp())
            payload = {
                "user_id": user.email,
                "email": user.email,
                "name": user.first_name,
                "exp": expires_at,
            }
            return jwt.encode(
                payload=payload, key=self.api_secret_key, algorithm="HS256"
            )
        except Exception as e:
            log.error(f"Error generating Intercom user token: {e}")
            return None


intercom_service = IntercomService()
