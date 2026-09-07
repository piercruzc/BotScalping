from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..parser import ParseError, parse_signal
from ..runtime import BotRuntime


STATIC_DIR = Path(__file__).resolve().parent / "static"


class ConfigPatch(BaseModel):
    symbol: str | None = None
    lot_size: float | None = Field(default=None, gt=0)
    pip_size: float | None = Field(default=None, gt=0)
    max_spread_pips: float | None = Field(default=None, ge=0)
    entry_tolerance: float | None = Field(default=None, ge=0)
    chase_buffer_pips: float | None = Field(default=None, ge=0)
    be_cushion_pips: float | None = Field(default=None, ge=0)
    deviation_points: int | None = Field(default=None, ge=0)
    trail_enabled: bool | None = None
    trail_start_pips: float | None = Field(default=None, ge=0)
    trail_distance_pips: float | None = Field(default=None, ge=0)
    dry_run: bool | None = None
    telegram_enabled: bool | None = None


class ModeBody(BaseModel):
    mode: str
    confirmation: str = ""


class SignalBody(BaseModel):
    text: str


def create_app(runtime: BotRuntime) -> FastAPI:
    app = FastAPI(title="Piply Scalp Desk", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/status")
    def status() -> dict:
        return runtime.status()

    @app.get("/api/logs")
    def logs() -> dict:
        return {"items": runtime.logs.list()}

    @app.put("/api/config")
    def update_config(body: ConfigPatch) -> dict:
        settings = runtime.config.update(body.model_dump(exclude_none=True))
        runtime.logs.info("Parámetros actualizados")
        return settings.to_public_dict()

    @app.post("/api/mode")
    def set_mode(body: ModeBody) -> dict:
        mode = body.mode.strip().lower()
        if mode not in {"demo", "real"}:
            raise HTTPException(400, "Modo inválido")
        if mode == "real":
            if body.confirmation.strip().upper() != "REAL":
                raise HTTPException(400, "Para activar Real escribe REAL")
            settings = runtime.config.set_mode("real", live_confirmed=True)
            runtime.logs.warn("Modo REAL confirmado. Solo se operará el canal de Telegram.")
        else:
            settings = runtime.config.set_mode("demo", live_confirmed=False)
            runtime.logs.info("Modo Demo activado")
        account = runtime.connect_mt5()
        return {
            "settings": settings.to_public_dict(),
            "account": account.__dict__,
        }

    @app.post("/api/preview")
    def preview(body: SignalBody) -> dict:
        if runtime.config.get().operating_mode != "demo":
            raise HTTPException(403, "Pegar señales solo está disponible en Demo")
        try:
            return runtime.preview(body.text)
        except ParseError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/execute")
    def execute(body: SignalBody) -> dict:
        settings = runtime.config.get()
        if settings.operating_mode != "demo":
            raise HTTPException(403, "En Real no se pegan señales. Solo Telegram.")
        try:
            signal = parse_signal(body.text, message_id=f"panel-{abs(hash(body.text)) % 10**8}")
        except ParseError as exc:
            raise HTTPException(400, str(exc)) from exc
        report = runtime.execute_signal(signal, source="panel")
        if report.rejected and not report.placed:
            raise HTTPException(409, report.rejected)
        return {
            "dry_run": report.dry_run,
            "rejected": report.rejected,
            "placed": report.placed,
            "skipped": report.skipped,
        }

    return app
