from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ActiveSignalState:
    message_id: str
    direction: str
    tp1: float
    sl: float
    token: str = ""
    entry: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    tickets: list[int] = field(default_factory=list)
    be_done: bool = False
    tp2_done: bool = False
    source: str = ""


@dataclass
class AppState:
    processed_ids: list[str] = field(default_factory=list)
    actives: list[ActiveSignalState] = field(default_factory=list)


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
        self.data = AppState(
            processed_ids=list(raw.get("processed_ids") or []),
            actives=_load_actives(raw),
        )

    def save(self) -> None:
        with self._lock:
            payload: dict[str, Any] = {
                "processed_ids": self.data.processed_ids[-400:],
                "actives": [asdict(item) for item in self.data.actives],
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

    def list_actives(self) -> list[ActiveSignalState]:
        with self._lock:
            return list(self.data.actives)

    def add_active(self, active: ActiveSignalState) -> None:
        with self._lock:
            self.data.actives.append(active)
            self.save()

    def update_active(self, active: ActiveSignalState) -> None:
        with self._lock:
            self.data.actives = [
                active if item.message_id == active.message_id else item
                for item in self.data.actives
            ]
            self.save()

    def remove_active(self, message_id: str) -> None:
        with self._lock:
            self.data.actives = [item for item in self.data.actives if item.message_id != message_id]
            self.save()


def signal_token(message_id: str) -> str:
    return (message_id or "x")[-8:]


_COMMENT_RE = re.compile(r"p\|([^|]+)\|(\d+)")


def comment_belongs(comment: str, token: str) -> bool:
    if not token:
        return False
    text = comment or ""
    if f"p|{token}|" in text:
        return True
    parsed = _COMMENT_RE.search(text)
    return bool(parsed and parsed.group(1) == token)


def comment_leg(comment: str) -> int | None:
    parsed = _COMMENT_RE.search(comment or "")
    if not parsed:
        return None
    return int(parsed.group(2))


def entries_overlap(direction: str, entry: float, other: ActiveSignalState, tolerance: float) -> bool:
    if other.direction != direction:
        return False
    return abs(other.entry - entry) <= tolerance


def _load_actives(raw: dict[str, Any]) -> list[ActiveSignalState]:
    if isinstance(raw.get("actives"), list):
        return [_active_from_dict(item) for item in raw["actives"] if isinstance(item, dict)]
    legacy = raw.get("active")
    if isinstance(legacy, dict):
        return [_active_from_dict(legacy)]
    return []


def _active_from_dict(raw: dict[str, Any]) -> ActiveSignalState:
    allowed = set(ActiveSignalState.__dataclass_fields__)
    item = ActiveSignalState(**{key: value for key, value in raw.items() if key in allowed})
    if not item.token:
        item.token = signal_token(item.message_id)
    cleaned: list[int] = []
    for value in item.tickets or []:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            continue
    item.tickets = cleaned
    return item
