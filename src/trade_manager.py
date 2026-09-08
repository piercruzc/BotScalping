from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .models import PositionSnapshot, Tick
from .safety import Safety, SafetyError
from .state import ActiveSignalState, comment_belongs

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
        market = runtime.mt5.tick(settings.symbol)
        if market is None:
            return
        all_pos = runtime.mt5.positions(settings.symbol, settings.magic)
        all_pend = runtime.mt5.pendings(settings.symbol, settings.magic)
        for active in runtime.state.list_actives():
            positions = [pos for pos in all_pos if comment_belongs(pos.comment, active.token)]
            pendings = [pend for pend in all_pend if comment_belongs(pend.comment, active.token)]
            if not positions and not pendings:
                runtime.state.remove_active(active.message_id)
                runtime.logs.info(f"Señal {active.token} cerrada")
                continue
            if not active.be_done and (
                _level_hit(active.direction, active.tp1, market) or _leg_closed(1, positions)
            ):
                self._move_to_break_even(active, positions, settings, account)
            if (
                active.be_done
                and not active.tp2_done
                and active.tp2
                and (_level_hit(active.direction, active.tp2, market) or _leg_closed(2, positions))
            ):
                self._lock_at_tp1(active, positions, settings, account)
            if settings.trail_enabled and active.tp2_done:
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
        if not _can_manage(settings, account, self.runtime, "BE"):
            return
        total_vol = sum(pos.volume for pos in positions)
        if total_vol <= 0:
            return
        avg = sum(pos.price_open * pos.volume for pos in positions) / total_vol
        cushion = settings.be_cushion_pips * settings.pip_size
        new_sl = sl_break_even(active.direction, avg, cushion)
        self._apply_sl(positions, new_sl, settings, f"SL a BE {new_sl:.2f} (media {avg:.2f})")
        active.be_done = True
        self.runtime.state.update_active(active)

    def _lock_at_tp1(
        self,
        active: ActiveSignalState,
        positions: list[PositionSnapshot],
        settings,
        account,
    ) -> None:
        if not positions:
            active.tp2_done = True
            self.runtime.state.update_active(active)
            return
        if not _can_manage(settings, account, self.runtime, "lock TP1"):
            return
        cushion = settings.be_cushion_pips * settings.pip_size
        new_sl = sl_lock_tp1(active.direction, active.tp1, cushion)
        self._apply_sl(
            positions,
            new_sl,
            settings,
            f"TP2 hecho: SL del runner a TP1 {new_sl:.2f} (TP3 sigue abierto)",
        )
        active.tp2_done = True
        self.runtime.state.update_active(active)

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
        if not _can_manage(settings, account, self.runtime, "trail"):
            return
        floor = sl_lock_tp1(active.direction, active.tp1, settings.be_cushion_pips * settings.pip_size)
        for pos in positions:
            new_sl = trail_stop(
                active.direction,
                pos.price_open,
                market,
                settings.trail_percent,
                settings.trail_distance_pips * settings.pip_size,
                floor,
            )
            if new_sl is None or not _sl_improves(active.direction, pos.sl, new_sl):
                continue
            try:
                result = self.runtime.mt5.modify_sl(pos.ticket, new_sl, pos.tp, settings)
                if result.get("ok"):
                    self.runtime.logs.info(f"Trail SL {new_sl:.2f} ticket {pos.ticket}")
            except Exception as exc:  # noqa: BLE001
                self.runtime.logs.error(f"Trail falló {pos.ticket}: {exc}")

    def _apply_sl(self, positions: list[PositionSnapshot], new_sl: float, settings, message: str) -> None:
        for pos in positions:
            try:
                result = self.runtime.mt5.modify_sl(pos.ticket, new_sl, pos.tp, settings)
                if result.get("ok"):
                    self.runtime.logs.info(f"{message} ticket {pos.ticket}")
            except Exception as exc:  # noqa: BLE001
                self.runtime.logs.error(f"No se pudo mover SL {pos.ticket}: {exc}")


def sl_break_even(direction: str, avg_entry: float, cushion: float) -> float:
    if direction == "BUY":
        return avg_entry - cushion
    return avg_entry + cushion


def sl_lock_tp1(direction: str, tp1: float, cushion: float) -> float:
    """Tras TP2, el SL del runner queda en TP1 (un colchón por spread)."""
    if direction == "BUY":
        return tp1 - cushion
    return tp1 + cushion


def trail_stop(
    direction: str,
    entry: float,
    market: Tick,
    trail_percent: float,
    trail_distance: float,
    floor: float,
) -> float | None:
    if direction == "BUY":
        price = market.bid
        profit = price - entry
        if profit <= 0:
            return None
        if trail_percent > 0:
            proposed = entry + profit * (trail_percent / 100.0)
        else:
            proposed = price - trail_distance
        return max(proposed, floor)
    price = market.ask
    profit = entry - price
    if profit <= 0:
        return None
    if trail_percent > 0:
        proposed = entry - profit * (trail_percent / 100.0)
    else:
        proposed = price + trail_distance
    return min(proposed, floor)


def _sl_improves(direction: str, current_sl: float, new_sl: float) -> bool:
    if direction == "BUY":
        return new_sl > current_sl
    return current_sl == 0 or new_sl < current_sl


def _level_hit(direction: str, level: float, tick: Tick) -> bool:
    if direction == "BUY":
        return tick.bid >= level
    return tick.ask <= level


def _leg_closed(leg: int, positions: list[PositionSnapshot]) -> bool:
    if not positions:
        return False
    marker = f"|{leg}"
    still_open = any((pos.comment or "").endswith(marker) for pos in positions)
    return not still_open


def _can_manage(settings, account, runtime, label: str) -> bool:
    try:
        Safety().assert_can_trade(settings, account, "manager")
    except SafetyError as exc:
        runtime.logs.warn(f"{label} bloqueado: {exc}")
        return False
    return True
