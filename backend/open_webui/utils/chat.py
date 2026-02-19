import logging
import sys

from typing import Any

from fastapi import Request

from beyond_the_loop.socket.main import (
    get_event_call,
    get_event_emitter,
)

from open_webui.env import SRC_LOG_LEVELS, GLOBAL_LOG_LEVEL


logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

async def chat_completed(request: Request, form_data: dict, user: Any):
    data = form_data

    __event_emitter__ = get_event_emitter(
        {
            "chat_id": data["chat_id"],
            "message_id": data["id"],
            "session_id": data["session_id"],
            "user_id": user.id,
        }
    )

    __event_call__ = get_event_call(
        {
            "chat_id": data["chat_id"],
            "message_id": data["id"],
            "session_id": data["session_id"],
            "user_id": user.id,
        }
    )

    return data