from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

from telethon import TelegramClient, events

from .parser import ParseError, parse_signal

if TYPE_CHECKING:
    from .runtime import BotRuntime


class TelegramListener:
    def __init__(self, runtime: BotRuntime) -> None:
        self.runtime = runtime
        self.client: TelegramClient | None = None
        self._seen_lock = asyncio.Lock()

    def configured(self) -> bool:
        return bool(
            os.getenv("TELEGRAM_API_ID")
            and os.getenv("TELEGRAM_API_HASH")
            and os.getenv("TELEGRAM_CHANNEL_ID")
        )

    async def start(self) -> None:
        if not self.configured():
            self.runtime.logs.warn(
                "Telegram no configurado. Completa TELEGRAM_* en .env para leer el canal."
            )
            while True:
                await asyncio.sleep(30)

        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        channel = _channel_ref(os.environ["TELEGRAM_CHANNEL_ID"])
        sessions = Path("sessions")
        sessions.mkdir(exist_ok=True)
        self.client = TelegramClient(str(sessions / "piply"), api_id, api_hash)
        await self.client.start()
        self.runtime.notify.bind(self.client)
        self.runtime.logs.info("Telegram conectado")

        @self.client.on(events.NewMessage(chats=channel))
        async def _on_new(event) -> None:  # type: ignore[no-untyped-def]
            await self._handle(event.message.id, event.raw_text or "")

        while True:
            settings = self.runtime.config.get()
            if settings.telegram_active:
                try:
                    async for message in self.client.iter_messages(channel, limit=5):
                        await self._handle(message.id, message.raw_text or "")
                except Exception as exc:  # noqa: BLE001
                    self.runtime.logs.error(f"Poll Telegram: {exc}")
            await asyncio.sleep(10)

    async def _handle(self, message_id: int, text: str) -> None:
        mid = str(message_id)
        async with self._seen_lock:
            if self.runtime.state.seen(mid):
                return
            if not text.strip():
                return
            settings = self.runtime.config.get()
            if not settings.telegram_active:
                return
            try:
                signal = parse_signal(text, message_id=mid)
            except ParseError:
                return
            self.runtime.state.mark(mid)
        self.runtime.logs.info(f"Señal Telegram {signal.direction} {signal.symbol}", source="telegram")
        report = self.runtime.execute_signal(signal, source="telegram")
        if report.rejected:
            self.runtime.logs.warn(report.rejected, source="telegram")
            await self.runtime.notify.send(f"Señal rechazada: {report.rejected}")
        else:
            placed = len(report.placed)
            self.runtime.logs.info(f"Telegram: {placed} órdenes enviadas", source="telegram")
            await self.runtime.notify.send(
                f"{signal.direction} {signal.symbol}: {placed} órdenes ({'dry-run' if report.dry_run else 'live'})"
            )


def _channel_ref(raw: str):
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw
