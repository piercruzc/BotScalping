from __future__ import annotations

import os
from typing import Optional


class Notifier:
    def __init__(self) -> None:
        self._client = None
        raw = os.getenv("NOTIFY_CHAT_ID", "").strip()
        self.chat_id: Optional[int] = int(raw) if raw.lstrip("-").isdigit() else None

    def bind(self, client) -> None:
        self._client = client

    async def send(self, message: str) -> None:
        if self._client is None or self.chat_id is None:
            return
        try:
            await self._client.send_message(self.chat_id, message)
        except Exception:
            return
