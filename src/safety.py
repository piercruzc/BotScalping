from __future__ import annotations

from .config import Settings
from .models import AccountSnapshot, SignalSource


class SafetyError(RuntimeError):
    pass


class Safety:
    def assert_can_trade(
        self,
        settings: Settings,
        account: AccountSnapshot,
        source: SignalSource,
        *,
        ignore_dry_run: bool = False,
    ) -> None:
        if not ignore_dry_run and settings.dry_run:
            raise SafetyError("Dry-run activo: no se envían órdenes")
        if not account.connected:
            raise SafetyError(account.error or "MT5 no está conectado")
        if settings.operating_mode == "demo" and not account.is_demo:
            raise SafetyError(
                "Modo Demo, pero MT5 está en cuenta REAL. Cambia el login o el switch."
            )
        if settings.operating_mode == "real":
            if account.is_demo:
                raise SafetyError(
                    "Modo Real, pero MT5 está en cuenta DEMO. Cambia el login o el switch."
                )
            if not settings.live_confirmed:
                raise SafetyError("Modo Real no confirmado. Escribe REAL en el panel.")
            if source == "panel":
                raise SafetyError(
                    "En Real no se pegan señales. Solo se opera el canal de Telegram."
                )

    def check_mode_alignment(
        self, settings: Settings, account: AccountSnapshot
    ) -> str | None:
        if not account.connected:
            return account.error or "MT5 no está conectado"
        if settings.operating_mode == "demo" and not account.is_demo:
            return "Switch en Demo, cuenta MT5 REAL"
        if settings.operating_mode == "real" and account.is_demo:
            return "Switch en Real, cuenta MT5 DEMO"
        if settings.operating_mode == "real" and not settings.live_confirmed:
            return "Modo Real sin confirmación"
        return None
