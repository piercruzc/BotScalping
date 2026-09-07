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
                rejected="El precio ya tocó TP1. Se cancela la señal.",
            )

        entry = choose_best_entry(signal, tick, settings)

        tps = (signal.tp1, signal.tp2, signal.tp3)
        orders = [
            _build_leg(signal, tick, settings, leg, entry, tp)
            for leg, tp in enumerate(tps, start=1)
        ]
        if not any(order.accepted for order in orders):
            return PlanResult(
                signal=signal,
                orders=orders,
                rejected="Ninguna de las 3 entradas es válida con el precio actual.",
            )
        return PlanResult(signal=signal, orders=orders)


def choose_best_entry(signal: Signal, tick: Tick, settings: Settings) -> float:
    """Elige FIRST o SECOND: si está cerca de una, esa; si de las dos, la mejor.

    BUY: mejor = más baja. SELL: mejor = más alta.
    Si está entre ambas, usa la mejor. Si está lejos, la más cercana
    (limit o stop). Solo se cancela la señal si ya tocó TP1.
    """
    ref = tick.ask if signal.direction == "BUY" else tick.bid
    first = signal.first_entry
    second = signal.second_entry
    near = max(settings.entry_tolerance, settings.near_entry_pips * settings.pip_size)
    d1 = abs(ref - first)
    d2 = abs(ref - second)
    near1 = d1 <= near
    near2 = d2 <= near
    better = min(first, second) if signal.direction == "BUY" else max(first, second)
    if near1 and near2:
        return better
    if near1:
        return first
    if near2:
        return second
    lo, hi = min(first, second), max(first, second)
    if lo <= ref <= hi:
        return better
    return first if d1 <= d2 else second


def _build_leg(
    signal: Signal,
    tick: Tick,
    settings: Settings,
    leg: int,
    entry: float,
    tp: float,
) -> PlannedOrder:
    volume = float(settings.lot_size)
    rr_error = _invalid_rr(signal, entry, tp)
    kind = _order_kind(signal.direction, entry, tick, settings.entry_tolerance)
    return PlannedOrder(
        leg=leg,
        side=signal.direction,
        kind=kind,
        entry=entry,
        sl=signal.sl,
        tp=tp,
        volume=volume,
        skip_reason=rr_error,
    )


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


def _invalid_rr(signal: Signal, entry: float, tp: float) -> str | None:
    if signal.direction == "BUY":
        if not (signal.sl < entry):
            return f"BUY inválido: SL {signal.sl} debe estar bajo la entrada {entry}"
        if not (entry < tp):
            return f"BUY inválido: entrada {entry} debe estar bajo TP {tp}"
        return None
    if not (signal.sl > entry):
        return f"SELL inválido: SL {signal.sl} debe estar sobre la entrada {entry}"
    if not (entry > tp):
        return f"SELL inválido: entrada {entry} debe estar sobre TP {tp}"
    return None


def skip_order(order: PlannedOrder, reason: str) -> PlannedOrder:
    return replace(order, skip_reason=reason)
