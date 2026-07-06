"""In-process event bus (observer pattern).

Domains (Sentry, Cortex, API) communicate through this bus instead of
importing each other, keeping the monolith modular.
"""

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

Handler = Callable[[str, Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        with self._lock:
            self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(event_type, [])) + list(
                self._subscribers.get("*", [])
            )
        for handler in handlers:
            try:
                handler(event_type, payload)
            except Exception:  # noqa: BLE001 - a bad subscriber must not kill the bus
                logger.exception("Event handler failed for %s", event_type)


# Module-level default bus for the single-process monolith.
bus = EventBus()
