from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ActiveSignalState:
    message_id: str
    direction: str
    tp1: float
    sl: float
    be_done: bool = False
    source: str = ""


@dataclass
class AppState:
    processed_ids: list[str] = field(default_factory=list)
    active: Optional[ActiveSignalState] = None


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = AppState()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        active = raw.get("active")
        self.data = AppState(
            processed_ids=list(raw.get("processed_ids") or []),
            active=ActiveSignalState(**active) if active else None,
        )

    def save(self) -> None:
        with self._lock:
            payload: dict[str, Any] = {
                "processed_ids": self.data.processed_ids[-400:],
                "active": asdict(self.data.active) if self.data.active else None,
            }
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def seen(self, message_id: str) -> bool:
        if not message_id:
            return False
        with self._lock:
            return message_id in self.data.processed_ids

    def mark(self, message_id: str) -> None:
        if not message_id:
            return
        with self._lock:
            if message_id not in self.data.processed_ids:
                self.data.processed_ids.append(message_id)
            self.save()

    def set_active(self, active: ActiveSignalState | None) -> None:
        with self._lock:
            self.data.active = active
            self.save()
