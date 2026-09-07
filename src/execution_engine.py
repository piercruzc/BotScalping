from __future__ import annotations

from dataclasses import replace

from .config import Settings
from .models import OrderKind, PlannedOrder, PlanResult, Signal, Tick


class ExecutionEngine:
    def plan(self, signal: Signal, tick: Tick, settings: Settings) -> PlanResult:
        pip = settings.pip_size
        spread_pips = tick.spread / pip if pip else 0.0
        if spread_pips > settings.max_spread_pips:
            return PlanResult(
                signal=signal,
                rejected=f"Spread {spread_pips:.1f} pips > máximo {settings.max_spread_pips}",
            )

        if _already_past_tp1(signal, tick):
            return PlanResult(
                signal=signal,
                rejected="El precio ya superó TP1. No se persigue la señal.",
            )

        chase = _chasing_away_from_zone(signal, tick, settings)
        legs = (
            (1, signal.first_entry, signal.tp1),
            (2, signal.mid_entry, signal.tp2),
            (3, signal.second_entry, None if settings.trail_enabled else signal.tp3),
        )
        orders: list[PlannedOrder] = []
        for leg, entry, tp in legs:
            orders.append(_build_leg(signal, tick, settings, leg, entry, tp, chase))
        if not any(order.accepted for order in orders):
            return PlanResult(
                signal=signal,
                orders=orders,
                rejected="Ninguna de las 3 entradas es válida con el precio actual.",
            )
        return PlanResult(signal=signal, orders=orders)


def _build_leg(
    signal: Signal,
    tick: Tick,
    settings: Settings,
    leg: int,
    entry: float,
    tp: float | None,
    chase: bool,
) -> PlannedOrder:
    volume = float(settings.lot_size)
    rr_error = _invalid_rr(signal, entry, tp)
    if rr_error:
        return PlannedOrder(
            leg=leg,
            side=signal.direction,
            kind="MARKET",
            entry=entry,
            sl=signal.sl,
            tp=tp,
            volume=volume,
            skip_reason=rr_error,
        )

    kind = _order_kind(signal.direction, entry, tick, settings.entry_tolerance)
    skip = None
    if chase and kind in {"MARKET", "BUY_STOP", "SELL_STOP"}:
        skip = "Fuera de zona: no se persigue con market/stop. Solo limits en la zona."
        if kind.endswith("LIMIT"):
            skip = None
        elif kind == "MARKET":
            skip = "Fuera de zona: no se compra/vende más caro. Solo limits."
    if chase and kind.endswith("LIMIT"):
        skip = None

    order = PlannedOrder(
        leg=leg,
        side=signal.direction,
        kind=kind,
        entry=entry,
        sl=signal.sl,
        tp=tp,
        volume=volume,
        skip_reason=skip,
    )
    return order


def _order_kind(direction: str, entry: float, tick: Tick, tolerance: float) -> OrderKind:
    if direction == "BUY":
        ref = tick.ask
        if abs(ref - entry) <= tolerance:
            return "MARKET"
        return "BUY_LIMIT" if ref > entry else "BUY_STOP"
    ref = tick.bid
    if abs(ref - entry) <= tolerance:
        return "MARKET"
    return "SELL_LIMIT" if ref < entry else "SELL_STOP"


def _already_past_tp1(signal: Signal, tick: Tick) -> bool:
    if signal.direction == "BUY":
        return tick.bid >= signal.tp1
    return tick.ask <= signal.tp1


def _chasing_away_from_zone(signal: Signal, tick: Tick, settings: Settings) -> bool:
    buffer = settings.chase_buffer_pips * settings.pip_size
    if signal.direction == "BUY":
        return tick.ask > signal.first_entry + buffer
    return tick.bid < signal.first_entry - buffer


def _invalid_rr(signal: Signal, entry: float, tp: float | None) -> str | None:
    if signal.direction == "BUY":
        if not (signal.sl < entry):
            return f"BUY inválido: SL {signal.sl} debe estar bajo la entrada {entry}"
        if tp is not None and not (entry < tp):
            return f"BUY inválido: entrada {entry} debe estar bajo TP {tp}"
        return None
    if not (signal.sl > entry):
        return f"SELL inválido: SL {signal.sl} debe estar sobre la entrada {entry}"
    if tp is not None and not (entry > tp):
        return f"SELL inválido: entrada {entry} debe estar sobre TP {tp}"
    return None


def skip_order(order: PlannedOrder, reason: str) -> PlannedOrder:
    return replace(order, skip_reason=reason)
