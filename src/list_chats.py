"""Lista canales/grupos de tu sesión de Telegram para copiar el ID correcto.

Uso (en la carpeta del proyecto, con .env ya creado):

    python -m src.list_chats
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


async def _run() -> None:
    load_dotenv(_root() / ".env")
    api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    if not api_id or not api_hash:
        raise SystemExit("Falta TELEGRAM_API_ID o TELEGRAM_API_HASH en .env")

    sessions = _root() / "sessions"
    sessions.mkdir(exist_ok=True)
    client = TelegramClient(str(sessions / "piply"), int(api_id), api_hash)
    await client.start()
    print("\nTus chats (usa el id de un CANAL, no de un usuario):\n")
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            kind = "CANAL"
        elif dialog.is_group:
            kind = "grupo"
        else:
            kind = "usuario"
        username = f" @{dialog.entity.username}" if getattr(dialog.entity, "username", None) else ""
        mark = "  <-- copia este id" if dialog.is_channel else ""
        print(f"[{kind}] {dialog.name}{username}")
        print(f"         TELEGRAM_CHANNEL_ID={dialog.id}{mark}\n")
    await client.disconnect()
    print("Pega en .env el TELEGRAM_CHANNEL_ID del canal VIP (línea CANAL).")
    print("NOTIFY_CHAT_ID es tu usuario, no el canal.")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
