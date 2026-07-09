import json
import redis
import uuid


class RedisLock:
    def __init__(self, redis_url, lock_name, timeout_secs):
        self.lock_name = lock_name
        self.lock_id = str(uuid.uuid4())
        self.timeout_secs = timeout_secs
        self.lock_obtained = False
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def aquire_lock(self):
        # nx=True will only set this key if it _hasn't_ already been set
        self.lock_obtained = self.redis.set(
            self.lock_name, self.lock_id, nx=True, ex=self.timeout_secs
        )
        return self.lock_obtained

    def renew_lock(self):
        # xx=True will only set this key if it _has_ already been set
        return self.redis.set(
            self.lock_name, self.lock_id, xx=True, ex=self.timeout_secs
        )

    def release_lock(self):
        lock_value = self.redis.get(self.lock_name)
        if lock_value and lock_value == self.lock_id:
            self.redis.delete(self.lock_name)


class RedisDict:
    def __init__(self, name, redis_url):
        self.name = name
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def __setitem__(self, key, value):
        serialized_value = json.dumps(value)
        self.redis.hset(self.name, key, serialized_value)

    def __getitem__(self, key):
        value = self.redis.hget(self.name, key)
        if value is None:
            raise KeyError(key)
        return json.loads(value)

    def __delitem__(self, key):
        result = self.redis.hdel(self.name, key)
        if result == 0:
            raise KeyError(key)

    def __contains__(self, key):
        return self.redis.hexists(self.name, key)

    def __len__(self):
        return self.redis.hlen(self.name)

    def keys(self):
        return self.redis.hkeys(self.name)

    def values(self):
        return [json.loads(v) for v in self.redis.hvals(self.name)]

    def items(self):
        return [(k, json.loads(v)) for k, v in self.redis.hgetall(self.name).items()]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self):
        self.redis.delete(self.name)

    def update(self, other=None, **kwargs):
        if other is not None:
            for k, v in other.items() if hasattr(other, "items") else other:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]


# Session state used to live inside two big Redis hashes (RedisDict). That had
# two problems: (1) hash fields cannot expire individually, so any sid that
# never reached the disconnect handler (SIGKILL, node eviction, autopilot
# rotation) leaked forever, and (2) USER_POOL had to be modified via
# read-modify-write, which lost sids under concurrent connects. The stores
# below replace that: per-sid Redis keys with TTL (SessionStore) and a Redis
# Set per user (UserSessionSet) — both atomic and self-healing.
_SESSION_TTL_SECONDS = 86400  # 24h; refreshed on every connect/user-join


class SessionStore:
    """sid → user_dump JSON, one Redis key per sid with a TTL.

    Any sid whose pod died without firing `disconnect` disappears after
    _SESSION_TTL_SECONDS instead of accumulating forever in Redis.
    """

    def __init__(self, prefix, redis_url, ttl_seconds=_SESSION_TTL_SECONDS):
        self.prefix = prefix
        self.ttl = ttl_seconds
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def _key(self, sid):
        return f"{self.prefix}:{sid}"

    def set(self, sid, value):
        self.redis.set(self._key(sid), json.dumps(value), ex=self.ttl)

    def get(self, sid, default=None):
        raw = self.redis.get(self._key(sid))
        if raw is None:
            return default
        return json.loads(raw)

    def delete(self, sid):
        return self.redis.delete(self._key(sid)) == 1

    def __contains__(self, sid):
        return bool(self.redis.exists(self._key(sid)))


class UserSessionSet:
    """user_id → SET of active sids, Redis-native atomic ops.

    Replaces `USER_POOL[user_id] = USER_POOL[user_id] + [sid]` (racy
    read-modify-write that produced duplicates via connect+user-join AND lost
    sids under concurrent connects). SADD is atomic and idempotent. TTL is
    refreshed on every add so an idle user drops out after 24h, and Redis
    removes the key automatically once the set becomes empty on SREM.
    """

    def __init__(self, prefix, redis_url, ttl_seconds=_SESSION_TTL_SECONDS):
        self.prefix = prefix
        self.ttl = ttl_seconds
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    def _key(self, user_id):
        return f"{self.prefix}:{user_id}"

    def add(self, user_id, sid):
        key = self._key(user_id)
        pipe = self.redis.pipeline()
        pipe.sadd(key, sid)
        pipe.expire(key, self.ttl)
        pipe.execute()

    def remove(self, user_id, sid):
        self.redis.srem(self._key(user_id), sid)

    def get_sids(self, user_id):
        return list(self.redis.smembers(self._key(user_id)))

    def has_user(self, user_id):
        return bool(self.redis.exists(self._key(user_id)))


class InMemorySessionStore:
    """Dev/test fallback for SessionStore when WEBSOCKET_MANAGER is unset."""

    def __init__(self, ttl_seconds=None):  # ttl ignored in-memory
        self._data = {}

    def set(self, sid, value):
        self._data[sid] = value

    def get(self, sid, default=None):
        return self._data.get(sid, default)

    def delete(self, sid):
        return self._data.pop(sid, None) is not None

    def __contains__(self, sid):
        return sid in self._data


class InMemoryUserSessionSet:
    """Dev/test fallback for UserSessionSet when WEBSOCKET_MANAGER is unset."""

    def __init__(self, ttl_seconds=None):
        self._data = {}

    def add(self, user_id, sid):
        self._data.setdefault(user_id, set()).add(sid)

    def remove(self, user_id, sid):
        sids = self._data.get(user_id)
        if not sids:
            return
        sids.discard(sid)
        if not sids:
            del self._data[user_id]

    def get_sids(self, user_id):
        return list(self._data.get(user_id, set()))

    def has_user(self, user_id):
        return user_id in self._data
