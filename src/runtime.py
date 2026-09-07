from __future__ import annotations

from pathlib import Path

from .config import ConfigStore, Settings
from .execution_engine import ExecutionEngine
from .logs import LogBuffer
from .models import (
    AccountSnapshot,
    ExecutionReport,
    PlannedOrder,
    PlanResult,
    Signal,
    SignalSource,
    Tick,
)
from .mt5_client import MT5Client
from .notify import Notifier
from .safety import Safety, SafetyError
from .state import ActiveSignalState, StateStore


class BotRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = ConfigStore(root / "config.yaml")
        self.state = StateStore(root / "state.json")
        self.logs = LogBuffer()
        self.mt5 = MT5Client()
        self.safety = Safety()
        self.engine = ExecutionEngine()
        self.notify = Notifier()
        self.telegram_status = {"connected": False, "channel": "", "error": ""}
        self.connect_mt5()

    def set_telegram_status(self, connected: bool, channel: str, error: str) -> None:
        self.telegram_status = {
            "connected": connected,
            "channel": channel,
            "error": error,
        }

    def connect_mt5(self) -> AccountSnapshot:
        account = self.mt5.connect(self.config.get())
        if account.connected:
            self.logs.info(
                f"MT5 {account.trade_mode} login {account.login} @ {account.server}"
            )
        else:
            self.logs.warn(account.error or "MT5 desconectado")
        return account

    def status(self) -> dict:
        settings = self.config.get()
        account = self.mt5.account()
        tick = self.mt5.tick(settings.symbol) if account.connected else None
        alignment = self.safety.check_mode_alignment(settings, account)
        positions = self.mt5.positions(settings.symbol, settings.magic) if account.connected else []
        pendings = self.mt5.pendings(settings.symbol, settings.magic) if account.connected else []
        spread_pips = None
        if tick and settings.pip_size:
            spread_pips = round(tick.spread / settings.pip_size, 2)
        return {
            "settings": settings.to_public_dict(),
            "account": {
                "connected": account.connected,
                "login": account.login,
                "server": account.server,
                "name": account.name,
                "balance": account.balance,
                "equity": account.equity,
                "is_demo": account.is_demo,
                "trade_mode": account.trade_mode,
                "error": account.error,
            },
            "tick": {"bid": tick.bid, "ask": tick.ask, "spread_pips": spread_pips} if tick else None,
            "alignment_error": alignment,
            "can_trade": alignment is None and account.connected and not settings.dry_run,
            "positions": [pos.__dict__ for pos in positions],
            "pendings": [pending.__dict__ for pending in pendings],
            "active": self.state.data.active.__dict__ if self.state.data.active else None,
            "mt5_available": self.mt5.available,
            "telegram": self.telegram_status,
        }

    def preview(self, text: str, message_id: str = "preview") -> dict:
        from .parser import parse_signal

        settings = self.config.get()
        signal = parse_signal(text, message_id=message_id)
        tick = self._require_tick(settings)
        plan = self.engine.plan(signal, tick, settings)
        return _plan_to_dict(plan, tick, settings)

    def execute_signal(self, signal: Signal, source: SignalSource) -> ExecutionReport:
        settings = self.config.get()
        account = self.mt5.account()
        if source == "panel" and settings.operating_mode == "real":
            rejected = "En Real no se pegan señales. Solo el canal de Telegram."
            self.logs.warn(rejected)
            return ExecutionReport(dry_run=settings.dry_run, source=source, rejected=rejected)

        try:
            self.safety.assert_can_trade(settings, account, source, ignore_dry_run=True)
        except SafetyError as exc:
            self.logs.warn(str(exc))
            return ExecutionReport(dry_run=settings.dry_run, source=source, rejected=str(exc))

        if self._busy(settings) and settings.max_concurrent_signals <= 1:
            rejected = "Ya hay una señal activa (posiciones o pendientes)."
            self.logs.warn(rejected)
            return ExecutionReport(dry_run=settings.dry_run, source=source, rejected=rejected)

        tick = self.mt5.tick(settings.symbol)
        if tick is None:
            rejected = "Sin precio de MT5. Abre el terminal y el símbolo."
            self.logs.error(rejected)
            return ExecutionReport(dry_run=settings.dry_run, source=source, rejected=rejected)

        plan = self.engine.plan(signal, tick, settings)
        if plan.rejected:
            self.logs.warn(plan.rejected)
            return ExecutionReport(dry_run=settings.dry_run, source=source, rejected=plan.rejected)

        skipped = [
            {"leg": order.leg, "reason": order.skip_reason, **_order_dict(order)}
            for order in plan.orders
            if not order.accepted
        ]
        if settings.dry_run:
            placed = [_order_dict(order) | {"status": "dry-run"} for order in plan.accepted_orders]
            self.logs.info(f"Dry-run {signal.direction}: {len(placed)} órdenes planificadas")
            return ExecutionReport(
                dry_run=True, source=source, rejected=None, placed=placed, skipped=skipped
            )

        try:
            self.safety.assert_can_trade(settings, account, source)
        except SafetyError as exc:
            return ExecutionReport(dry_run=False, source=source, rejected=str(exc))

        placed: list[dict] = []
        for order in plan.accepted_orders:
            comment = _comment(signal, order)
            try:
                result = self.mt5.place(order, settings, comment)
                placed.append({**_order_dict(order), **result})
                if result.get("ok"):
                    self.logs.info(
                        f"L{order.leg} {order.kind} {order.entry} lot {order.volume} ok"
                    )
                else:
                    self.logs.error(
                        f"L{order.leg} rechazada retcode={result.get('retcode')} {result.get('comment')}"
                    )
            except Exception as exc:  # noqa: BLE001
                self.logs.error(f"L{order.leg} error: {exc}")
                placed.append({**_order_dict(order), "ok": False, "error": str(exc)})

        if any(item.get("ok") for item in placed):
            self.state.set_active(
                ActiveSignalState(
                    message_id=signal.message_id or f"panel-{source}",
                    direction=signal.direction,
                    tp1=signal.tp1,
                    sl=signal.sl,
                    be_done=False,
                    source=source,
                )
            )
        return ExecutionReport(
            dry_run=False, source=source, rejected=None, placed=placed, skipped=skipped
        )

    def _busy(self, settings: Settings) -> bool:
        if self.state.data.active:
            return True
        if not self.mt5.account().connected:
            return False
        return bool(
            self.mt5.positions(settings.symbol, settings.magic)
            or self.mt5.pendings(settings.symbol, settings.magic)
        )

    def _require_tick(self, settings: Settings) -> Tick:
        tick = self.mt5.tick(settings.symbol)
        if tick is None:
            raise RuntimeError(
                "Sin precio de MT5. Abre MetaTrader 5, loguéate y deja XAUUSD en Market Watch."
            )
        return tick


def _comment(signal: Signal, order: PlannedOrder) -> str:
    token = (signal.message_id or "x")[-8:]
    return f"p|{token}|{order.leg}"


def _order_dict(order: PlannedOrder) -> dict:
    return {
        "leg": order.leg,
        "side": order.side,
        "kind": order.kind,
        "entry": order.entry,
        "sl": order.sl,
        "tp": order.tp,
        "volume": order.volume,
        "skip_reason": order.skip_reason,
    }


def _plan_to_dict(plan: PlanResult, tick: Tick, settings: Settings) -> dict:
    return {
        "rejected": plan.rejected,
        "direction": plan.signal.direction,
        "symbol": settings.symbol,
        "tick": {"bid": tick.bid, "ask": tick.ask},
        "lot_size": settings.lot_size,
        "orders": [_order_dict(order) for order in plan.orders],
        "accepted": len(plan.accepted_orders),
    }
