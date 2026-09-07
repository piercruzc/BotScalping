from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User

from .parser import ParseError, parse_signal
from .telegram_ids import channel_candidates

if TYPE_CHECKING:
    from .runtime import BotRuntime


class TelegramListener:
    def __init__(self, runtime: BotRuntime) -> None:
        self.runtime = runtime
        self.client: TelegramClient | None = None
        self._seen_lock = asyncio.Lock()
        self._entity: Any = None

    def configured(self) -> bool:
        return bool(
            os.getenv("TELEGRAM_API_ID")
            and os.getenv("TELEGRAM_API_HASH")
            and os.getenv("TELEGRAM_CHANNEL_ID")
        )

    async def start(self) -> None:
        if not self.configured():
            self.runtime.set_telegram_status(
                False, "", "Completa TELEGRAM_API_ID, TELEGRAM_API_HASH y TELEGRAM_CHANNEL_ID en .env"
            )
            self.runtime.logs.warn("Telegram no configurado. Completa TELEGRAM_* en .env.")
            while True:
                await asyncio.sleep(30)

        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
        raw_channel = os.environ["TELEGRAM_CHANNEL_ID"].strip()
        sessions = Path("sessions")
        sessions.mkdir(exist_ok=True)
        self.client = TelegramClient(str(sessions / "piply"), api_id, api_hash)
        await self.client.start()
        self.runtime.notify.bind(self.client)
        self.runtime.logs.info("Sesión de Telegram iniciada. Resolviendo el canal...")

        try:
            self._entity = await resolve_channel(self.client, raw_channel)
        except Exception as exc:  # noqa: BLE001
            message = (
                f"No pude abrir el canal '{raw_channel}': {exc}. "
                "Ese valor parece un usuario, no el canal VIP. "
                "Para listar tus canales: python -m src.list_chats"
            )
            self.runtime.set_telegram_status(False, "", message)
            self.runtime.logs.error(message)
            while True:
                await asyncio.sleep(30)

        title = _entity_title(self._entity)
        self.runtime.set_telegram_status(True, title, "")
        self.runtime.logs.info(f"Telegram conectado al canal: {title} (id={self._entity.id})")

        @self.client.on(events.NewMessage(chats=self._entity))
        async def _on_new(event) -> None:  # type: ignore[no-untyped-def]
            await self._handle(event.message.id, event.raw_text or "")

        while True:
            settings = self.runtime.config.get()
            if settings.telegram_active:
                try:
                    async for message in self.client.iter_messages(self._entity, limit=5):
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


async def resolve_channel(client: TelegramClient, raw: str):
    await client.get_dialogs()
    errors: list[str] = []
    for candidate in channel_candidates(raw):
        try:
            entity = await client.get_entity(candidate)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
            continue
        if isinstance(entity, User):
            errors.append(
                f"{candidate} es un usuario (PeerUser), no un canal. "
                "TELEGRAM_CHANNEL_ID debe ser el ID del canal VIP, casi siempre -100..."
            )
            continue
        if isinstance(entity, (Channel, Chat)):
            return entity
        errors.append(f"{candidate}: tipo no soportado {type(entity).__name__}")
    detail = " | ".join(errors) if errors else "sin candidatos"
    raise RuntimeError(detail)


def _entity_title(entity: Any) -> str:
    return getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)
