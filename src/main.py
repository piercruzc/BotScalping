from __future__ import annotations

import asyncio
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from .panel.app import create_app
from .runtime import BotRuntime
from .telegram_listener import TelegramListener
from .trade_manager import TradeManager


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


async def _async_main() -> None:
    load_dotenv(_root() / ".env")
    runtime = BotRuntime(_root())
    settings = runtime.config.get()
    app = create_app(runtime)
    listener = TelegramListener(runtime)
    manager = TradeManager(runtime)

    config = uvicorn.Config(
        app,
        host=settings.panel_host,
        port=settings.panel_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    runtime.logs.info(f"Panel en http://{settings.panel_host}:{settings.panel_port}")

    await asyncio.gather(
        server.serve(),
        listener.start(),
        manager.run(),
    )


def main() -> None:
    os.chdir(_root())
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
