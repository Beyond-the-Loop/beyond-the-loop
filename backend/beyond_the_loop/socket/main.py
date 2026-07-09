import asyncio
import socketio
import logging
import sys

from beyond_the_loop.models.users import Users, UserNameResponse
from open_webui.env import REDIS_URL
from open_webui.models.channels import Channels
from beyond_the_loop.models.chats import Chats

from open_webui.env import (
    ENABLE_WEBSOCKET_SUPPORT,
    WEBSOCKET_MANAGER,
)
from open_webui.utils.auth import decode_token
from beyond_the_loop.socket.utils import (
    RedisDict,
    SessionStore,
    UserSessionSet,
    InMemorySessionStore,
    InMemoryUserSessionSet,
)
from beyond_the_loop.observability.metrics import websocket_connections

from open_webui.env import (
    GLOBAL_LOG_LEVEL,
    SRC_LOG_LEVELS,
)


logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["SOCKET"])


if WEBSOCKET_MANAGER == "redis":
    mgr = socketio.AsyncRedisManager(REDIS_URL)
    sio = socketio.AsyncServer(
        cors_allowed_origins=[],
        async_mode="asgi",
        transports=(["websocket"] if ENABLE_WEBSOCKET_SUPPORT else ["polling"]),
        allow_upgrades=ENABLE_WEBSOCKET_SUPPORT,
        always_connect=True,
        client_manager=mgr,
    )
else:
    sio = socketio.AsyncServer(
        cors_allowed_origins=[],
        async_mode="asgi",
        transports=(["websocket"] if ENABLE_WEBSOCKET_SUPPORT else ["polling"]),
        allow_upgrades=ENABLE_WEBSOCKET_SUPPORT,
        always_connect=True,
    )

COMPANY_CONFIG_CACHE = RedisDict("company_config_cache", redis_url=REDIS_URL)

STRIPE_COMPANY_ACTIVE_SUBSCRIPTION_CACHE = RedisDict(":stripe_company_active_subscription_cache", redis_url=REDIS_URL)
STRIPE_COMPANY_TRIAL_SUBSCRIPTION_CACHE = RedisDict(":stripe_company_trial_subscription_cache", redis_url=REDIS_URL)
STRIPE_PRODUCT_CACHE = RedisDict(":stripe_product_cache", redis_url=REDIS_URL)

# Dictionary to maintain the user pool

if WEBSOCKET_MANAGER == "redis":
    log.debug("Using Redis to manage websockets.")
    # Per-sid keys with TTL replace the old `open-webui:session_pool` /
    # `open-webui:user_pool` hashes. Prefix intentionally different so a
    # rolling deploy does not read the old hash and mistake it for a fresh
    # store — the old keys were leaking anyway; leftovers expire naturally.
    SESSION_POOL = SessionStore("open-webui:session", redis_url=REDIS_URL)
    USER_POOL = UserSessionSet("open-webui:user_sessions", redis_url=REDIS_URL)
else:
    SESSION_POOL = InMemorySessionStore()
    USER_POOL = InMemoryUserSessionSet()


app = socketio.ASGIApp(
    sio,
    socketio_path="/ws/socket.io",
)


def _register_session(sid, user):
    """Store the session in SESSION_POOL / USER_POOL. Idempotent — SADD in
    UserSessionSet deduplicates automatically, so calling this from both
    `connect` and `user-join` is safe (unlike the previous list-based code
    that appended duplicates on every reconnect)."""
    user_dump = user.model_dump()
    SESSION_POOL.set(sid, user_dump)
    USER_POOL.add(user.id, sid)


@sio.event
async def connect(sid, environ, auth):
    websocket_connections.inc()
    if not auth or "token" not in auth:
        return
    data = decode_token(auth["token"])
    if data is None or "id" not in data:
        return
    user = await asyncio.to_thread(Users.get_user_by_id, data["id"])
    if not user:
        return
    await asyncio.to_thread(_register_session, sid, user)
    log.debug(f"user {user.id} connected with session ID {sid}")


@sio.on("user-join")
async def user_join(sid, data):
    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    token_data = decode_token(auth["token"])
    if token_data is None or "id" not in token_data:
        return

    user = await asyncio.to_thread(Users.get_user_by_id, token_data["id"])
    if not user:
        return

    # Re-register defensively: the frontend emits `user-join` right after
    # `connect`. In normal flow `connect` already registered this sid, but
    # if the connect handler skipped registration (e.g. transient auth
    # decode issue) this is our safety net. SADD is idempotent, so this
    # no longer produces duplicates like the old list-append code did.
    await asyncio.to_thread(_register_session, sid, user)

    channels = await asyncio.to_thread(Channels.get_channels_by_user_id, user.id)
    log.debug(f"{channels=}")
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")

    log.debug(f"user {user.email}({user.id}) joined rooms")
    return {"id": user.id, "first_name": user.first_name, "last_name": user.last_name}


@sio.on("join-channels")
async def join_channel(sid, data):
    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    data = decode_token(auth["token"])
    if data is None or "id" not in data:
        return

    user = await asyncio.to_thread(Users.get_user_by_id, data["id"])
    if not user:
        return

    channels = await asyncio.to_thread(Channels.get_channels_by_user_id, user.id)
    log.debug(f"{channels=}")
    for channel in channels:
        await sio.enter_room(sid, f"channel:{channel.id}")


@sio.on("channel-events")
async def channel_events(sid, data):
    room = f"channel:{data['channel_id']}"
    participants = sio.manager.get_participants(
        namespace="/",
        room=room,
    )

    sids = [sid for sid, _ in participants]
    if sid not in sids:
        return

    event_data = data["data"]
    event_type = event_data["type"]

    if event_type == "typing":
        session_user = await asyncio.to_thread(SESSION_POOL.get, sid, None)
        if session_user is None:
            return
        await sio.emit(
            "channel-events",
            {
                "channel_id": data["channel_id"],
                "message_id": data.get("message_id", None),
                "data": event_data,
                "user": UserNameResponse(**session_user).model_dump(),
            },
            room=room,
        )


@sio.event
async def disconnect(sid):
    websocket_connections.dec()

    def _unregister_session():
        user = SESSION_POOL.get(sid)
        if user is None:
            return False
        SESSION_POOL.delete(sid)
        USER_POOL.remove(user["id"], sid)
        return True

    unregistered = await asyncio.to_thread(_unregister_session)
    if not unregistered:
        log.debug(f"Unknown session ID {sid} disconnected")


def get_event_emitter(request_info):
    async def __event_emitter__(event_data):
        user_id = request_info["user_id"]
        session_ids_from_pool = await asyncio.to_thread(USER_POOL.get_sids, user_id)
        session_ids = list(
            set(session_ids_from_pool + [request_info["session_id"]])
        )

        for session_id in session_ids:
            await sio.emit(
                "chat-events",
                {
                    "chat_id": request_info["chat_id"],
                    "message_id": request_info["message_id"],
                    "data": event_data,
                },
                to=session_id,
            )

        if "type" in event_data and event_data["type"] == "status":
            await asyncio.to_thread(
                Chats.add_message_status_to_chat_by_id_and_message_id,
                request_info["chat_id"],
                request_info["message_id"],
                event_data.get("data", {}),
            )

        if "type" in event_data and event_data["type"] == "message":
            message = await asyncio.to_thread(
                Chats.get_message_by_id_and_message_id,
                request_info["chat_id"],
                request_info["message_id"],
            )

            content = message.get("content", "")
            content += event_data.get("data", {}).get("content", "")

            await asyncio.to_thread(
                Chats.upsert_message_to_chat_by_id_and_message_id,
                request_info["chat_id"],
                request_info["message_id"],
                {"content": content},
            )

        if "type" in event_data and event_data["type"] == "replace":
            content = event_data.get("data", {}).get("content", "")

            await asyncio.to_thread(
                Chats.upsert_message_to_chat_by_id_and_message_id,
                request_info["chat_id"],
                request_info["message_id"],
                {"content": content},
            )

    return __event_emitter__


# Explicit short timeout for sio.call. Without it, python-socketio defaults
# to 60s. When the target sid is stale (client disconnected but the sid
# hasn't been evicted by the socketio manager yet — very common after pod
# rotation), every chat completion path that goes through event_call would
# block for the full 60s. Chat requests appeared to "load forever" in the
# browser as a result. 5s is enough for a healthy client to round-trip.
_EVENT_CALL_TIMEOUT_SECONDS = 5


def get_event_call(request_info):
    async def __event_caller__(event_data):
        try:
            return await sio.call(
                "chat-events",
                {
                    "chat_id": request_info["chat_id"],
                    "message_id": request_info["message_id"],
                    "data": event_data,
                },
                to=request_info["session_id"],
                timeout=_EVENT_CALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            log.warning(
                f"sio.call timed out (sid={request_info['session_id']}, "
                f"chat_id={request_info['chat_id']}); client is likely gone"
            )
            return None

    return __event_caller__


get_event_caller = get_event_call


def get_user_id_from_session_pool(sid):
    user = SESSION_POOL.get(sid)
    if user:
        return user["id"]
    return None


def get_user_ids_from_room(room):
    active_session_ids = sio.manager.get_participants(
        namespace="/",
        room=room,
    )

    active_user_ids = list(
        set(
            [SESSION_POOL.get(session_id[0])["id"] for session_id in active_session_ids]
        )
    )
    return active_user_ids


def get_active_status_by_user_id(user_id):
    return USER_POOL.has_user(user_id)
