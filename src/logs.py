from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


class LogBuffer:
    def __init__(self, maxlen: int = 200) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, level: str, message: str, **extra: Any) -> dict[str, Any]:
        item = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            **extra,
        }
        with self._lock:
            self._items.appendleft(item)
        return item

    def info(self, message: str, **extra: Any) -> dict[str, Any]:
        return self.add("info", message, **extra)

    def warn(self, message: str, **extra: Any) -> dict[str, Any]:
        return self.add("warn", message, **extra)

    def error(self, message: str, **extra: Any) -> dict[str, Any]:
        return self.add("error", message, **extra)

    def list(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)[:limit]
