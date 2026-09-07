from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .models import PositionSnapshot, Tick
from .safety import Safety, SafetyError
from .state import ActiveSignalState

if TYPE_CHECKING:
    from .runtime import BotRuntime


class TradeManager:
    def __init__(self, runtime: BotRuntime) -> None:
        self.runtime = runtime

    async def run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001
                self.runtime.logs.error(f"Gestor: {exc}")
            await asyncio.sleep(1)

    def tick(self) -> None:
        runtime = self.runtime
        settings = runtime.config.get()
        account = runtime.mt5.account()
        active = runtime.state.data.active
        if active is None:
            return
        positions = runtime.mt5.positions(settings.symbol, settings.magic)
        pendings = runtime.mt5.pendings(settings.symbol, settings.magic)
        if not positions and not pendings:
            runtime.state.set_active(None)
            runtime.logs.info("Señal cerrada: sin posiciones ni pendientes")
            return
        market = runtime.mt5.tick(settings.symbol)
        if market is None:
            return
        if not active.be_done and (_tp1_hit(active, market) or _leg1_closed(active, positions)):
            self._move_to_break_even(active, positions, settings, account)
        if settings.trail_enabled:
            self._trail(active, positions, market, settings, account)

    def _move_to_break_even(
        self,
        active: ActiveSignalState,
        positions: list[PositionSnapshot],
        settings,
        account,
    ) -> None:
        if not positions:
            return
        safety = Safety()
        try:
            safety.assert_can_trade(settings, account, "manager")
        except SafetyError as exc:
            self.runtime.logs.warn(f"BE bloqueado: {exc}")
            return
        total_vol = sum(pos.volume for pos in positions)
        if total_vol <= 0:
            return
        avg = sum(pos.price_open * pos.volume for pos in positions) / total_vol
        cushion = settings.be_cushion_pips * settings.pip_size
        if active.direction == "BUY":
            new_sl = avg - cushion
        else:
            new_sl = avg + cushion
        for pos in positions:
            try:
                result = self.runtime.mt5.modify_sl(pos.ticket, new_sl, pos.tp, settings)
                if result.get("ok"):
                    self.runtime.logs.info(
                        f"SL a BE {new_sl:.2f} en ticket {pos.ticket} (media {avg:.2f})"
                    )
            except Exception as exc:  # noqa: BLE001
                self.runtime.logs.error(f"No se pudo mover SL {pos.ticket}: {exc}")
        active.be_done = True
        self.runtime.state.set_active(active)

    def _trail(
        self,
        active: ActiveSignalState,
        positions: list[PositionSnapshot],
        market: Tick,
        settings,
        account,
    ) -> None:
        if not positions:
            return
        safety = Safety()
        try:
            safety.assert_can_trade(settings, account, "manager")
        except SafetyError:
            return
        start = settings.trail_start_pips * settings.pip_size
        distance = settings.trail_distance_pips * settings.pip_size
        for pos in positions:
            if not _is_runner(pos):
                continue
            if active.direction == "BUY":
                profit = market.bid - pos.price_open
                if profit < start:
                    continue
                new_sl = market.bid - distance
                if new_sl <= pos.sl:
                    continue
            else:
                profit = pos.price_open - market.ask
                if profit < start:
                    continue
                new_sl = market.ask + distance
                if pos.sl and new_sl >= pos.sl:
                    continue
            try:
                result = self.runtime.mt5.modify_sl(pos.ticket, new_sl, 0.0, settings)
                if result.get("ok"):
                    self.runtime.logs.info(f"Trail SL {new_sl:.2f} ticket {pos.ticket}")
            except Exception as exc:  # noqa: BLE001
                self.runtime.logs.error(f"Trail falló {pos.ticket}: {exc}")


def _tp1_hit(active: ActiveSignalState, tick: Tick) -> bool:
    if active.direction == "BUY":
        return tick.bid >= active.tp1
    return tick.ask <= active.tp1


def _leg1_closed(active: ActiveSignalState, positions: list[PositionSnapshot]) -> bool:
    if not positions:
        return False
    has_leg1 = any("|1" in (pos.comment or "") or pos.comment.endswith("1") for pos in positions)
    return not has_leg1 and bool(positions)


def _is_runner(pos: PositionSnapshot) -> bool:
    comment = pos.comment or ""
    return comment.endswith("|3") or comment.endswith("3")
