import json
import threading
import time
from typing import Any

from app.queue import get_queue, read_events


class EventWorker:
    def __init__(self, queue=None, callback=None):
        self.queue = queue or get_queue()
        self.callback = callback or self._default_callback
        self._stop_event = threading.Event()
        self._thread = None

    def _default_callback(self, event: dict[str, Any]) -> None:
        print(f"Processed event: {event.get('event_type')} -> {event.get('payload')}")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        while not self._stop_event.is_set():
            events = self.queue.read(limit=10)
            for event in events:
                self.callback(event)
            time.sleep(0.2)


def process_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    event_type = event.get("event_type")
    return {
        "status": "processed",
        "event_type": event_type,
        "payload": payload,
    }
