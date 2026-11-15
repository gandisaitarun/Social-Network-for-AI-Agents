import json
import os
from threading import Lock
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover - optional for local non-queue runs
    redis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "agent_network:events")


class InMemoryEventQueue:
    def __init__(self):
        self._messages: list[dict[str, Any]] = []
        self._lock = Lock()

    def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"event_type": event_type, "payload": payload}
        with self._lock:
            self._messages.append(event)
        return event

    def read(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            unread = self._messages[:limit]
            self._messages = self._messages[limit:]
            return unread

    def clear(self):
        with self._lock:
            self._messages.clear()


class RedisEventQueue:
    def __init__(self, url: str = REDIS_URL):
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def _safe_call(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except Exception:
            return None

    def publish(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        entry = {"event_type": event_type, "payload": json.dumps(payload)}
        message_id = self._safe_call(self.client.xadd, STREAM_KEY, entry)
        return {"id": message_id, **entry}

    def read(self, limit: int = 10) -> list[dict[str, Any]]:
        entries = self._safe_call(self.client.xrange, STREAM_KEY, min="-", max="+", count=limit)
        if not entries:
            return []

        ordered = []
        for message_id, fields in entries:
            payload = fields.get("payload")
            event_type = fields.get("event_type")
            ordered.append({
                "id": message_id,
                "event_type": event_type,
                "payload": json.loads(payload) if payload else {},
            })

        self._safe_call(self.client.xdel, STREAM_KEY, *[message_id for message_id, _ in entries])
        return ordered

    def clear(self):
        self._safe_call(self.client.delete, STREAM_KEY)


fallback_queue = InMemoryEventQueue()


def get_queue():
    if redis is None:
        return fallback_queue

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        client.ping()
        return RedisEventQueue(REDIS_URL)
    except Exception:
        return fallback_queue


queue = get_queue()


def publish_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return queue.publish(event_type, payload)


def read_events(limit: int = 10) -> list[dict[str, Any]]:
    return queue.read(limit=limit)


def clear_events():
    queue.clear()
