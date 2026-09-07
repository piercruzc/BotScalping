from __future__ import annotations

import os
import time
from typing import Any, Optional

from .config import Settings
from .models import (
    AccountSnapshot,
    PendingSnapshot,
    PlannedOrder,
    PositionSnapshot,
    Tick,
)

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover - solo existe en Windows
    mt5 = None


# ACCOUNT_TRADE_MODE_DEMO = 0, CONTEST = 1, REAL = 2
_TRADE_MODE_DEMO = 0
_TRADE_MODE_REAL = 2


class MT5Client:
    def __init__(self) -> None:
        self.available = mt5 is not None
        self._connected = False

    def connect(self, settings: Settings) -> AccountSnapshot:
        if mt5 is None:
            self._connected = False
            return AccountSnapshot(
                connected=False,
                error="El paquete MetaTrader5 solo funciona en Windows con el terminal abierto.",
            )
        kwargs: dict[str, Any] = {}
        path = os.getenv("MT5_PATH", "").strip()
        if path:
            kwargs["path"] = path
        login, password, server = _credentials_for_mode(settings.operating_mode)
        if login:
            kwargs["login"] = login
        if password:
            kwargs["password"] = password
        if server:
            kwargs["server"] = server
        attempts = 6 if path else 2
        ok = False
        last = ""
        for attempt in range(attempts):
            ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
            if ok:
                break
            last = str(mt5.last_error())
            time.sleep(2)
        if not ok:
            self._connected = False
            hint = (
                " Abre MT5 a mano o revisa MT5_PATH + MT5_DEMO_LOGIN/PASSWORD/SERVER. "
                "El path debe ser terminal64.exe de Vantage."
            )
            return AccountSnapshot(connected=False, error=f"{last}.{hint}")
        symbol = settings.symbol
        if not mt5.symbol_select(symbol, True):
            self._connected = False
            return AccountSnapshot(
                connected=False,
                error=f"No se pudo seleccionar {symbol}. Revísalo en Market Watch.",
            )
        self._connected = True
        return self.account()

    def shutdown(self) -> None:
        if mt5 is not None and self._connected:
            mt5.shutdown()
        self._connected = False

    def account(self) -> AccountSnapshot:
        if mt5 is None or not self._connected:
            return AccountSnapshot(
                connected=False,
                error="MT5 no está conectado",
            )
        info = mt5.account_info()
        if info is None:
            return AccountSnapshot(connected=False, error=str(mt5.last_error()))
        mode = int(info.trade_mode)
        is_demo = mode != _TRADE_MODE_REAL
        label = {0: "demo", 1: "contest", 2: "real"}.get(mode, str(mode))
        return AccountSnapshot(
            connected=True,
            login=int(info.login),
            server=str(info.server),
            name=str(info.name),
            balance=float(info.balance),
            equity=float(info.equity),
            is_demo=is_demo,
            trade_mode=label,
        )

    def tick(self, symbol: str) -> Optional[Tick]:
        if mt5 is None or not self._connected:
            return None
        data = mt5.symbol_info_tick(symbol)
        if data is None:
            return None
        return Tick(bid=float(data.bid), ask=float(data.ask))

    def symbol_meta(self, symbol: str) -> dict[str, Any]:
        if mt5 is None or not self._connected:
            return {"digits": 2, "point": 0.01, "volume_min": 0.01, "volume_step": 0.01}
        info = mt5.symbol_info(symbol)
        if info is None:
            return {"digits": 2, "point": 0.01, "volume_min": 0.01, "volume_step": 0.01}
        return {
            "digits": int(info.digits),
            "point": float(info.point),
            "volume_min": float(info.volume_min),
            "volume_step": float(info.volume_step),
            "filling_mode": int(info.filling_mode),
        }

    def positions(self, symbol: str, magic: int) -> list[PositionSnapshot]:
        if mt5 is None or not self._connected:
            return []
        rows = mt5.positions_get(symbol=symbol) or []
        out: list[PositionSnapshot] = []
        for row in rows:
            if int(row.magic) != magic:
                continue
            side = "BUY" if int(row.type) == 0 else "SELL"
            out.append(
                PositionSnapshot(
                    ticket=int(row.ticket),
                    symbol=str(row.symbol),
                    side=side,  # type: ignore[arg-type]
                    volume=float(row.volume),
                    price_open=float(row.price_open),
                    sl=float(row.sl),
                    tp=float(row.tp),
                    profit=float(row.profit),
                    comment=str(row.comment),
                    magic=int(row.magic),
                )
            )
        return out

    def pendings(self, symbol: str, magic: int) -> list[PendingSnapshot]:
        if mt5 is None or not self._connected:
            return []
        rows = mt5.orders_get(symbol=symbol) or []
        out: list[PendingSnapshot] = []
        for row in rows:
            if int(row.magic) != magic:
                continue
            out.append(
                PendingSnapshot(
                    ticket=int(row.ticket),
                    symbol=str(row.symbol),
                    kind=_pending_kind(int(row.type)),
                    volume=float(row.volume_current or row.volume_initial),
                    price=float(row.price_open),
                    sl=float(row.sl),
                    tp=float(row.tp),
                    comment=str(row.comment),
                    magic=int(row.magic),
                )
            )
        return out

    def place(self, order: PlannedOrder, settings: Settings, comment: str) -> dict[str, Any]:
        if mt5 is None or not self._connected:
            raise RuntimeError("MT5 no está conectado")
        meta = self.symbol_meta(settings.symbol)
        volume = _normalize_volume(order.volume, meta)
        price = _round_price(order.entry, meta["digits"])
        sl = _round_price(order.sl, meta["digits"])
        tp = _round_price(order.tp, meta["digits"]) if order.tp is not None else 0.0
        filling = _filling_type(meta.get("filling_mode", 0))
        request = _build_request(order, settings, price, sl, tp, volume, comment, filling)
        check = mt5.order_check(request)
        if check is None:
            raise RuntimeError(f"order_check falló: {mt5.last_error()}")
        if int(check.retcode) != 0 and int(getattr(check, "retcode", 0)) not in {0}:
            # 0 = done for check on some builds; TRADE_RETCODE_DONE = 10009 is send, not check
            pass
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"order_send falló: {mt5.last_error()}")
        retcode = int(result.retcode)
        if retcode in {10004, 10021}:  # requote / price changed
            tick = self.tick(settings.symbol)
            if tick and order.kind == "MARKET":
                request["price"] = tick.ask if order.side == "BUY" else tick.bid
                result = mt5.order_send(request)
                if result is None:
                    raise RuntimeError(f"reintento falló: {mt5.last_error()}")
                retcode = int(result.retcode)
        if retcode == 10030:  # unsupported filling
            for alt in (0, 1, 2):
                if alt == filling:
                    continue
                request["type_filling"] = alt
                result = mt5.order_send(request)
                if result and int(result.retcode) in {10009, 10008}:
                    retcode = int(result.retcode)
                    break
        ok = retcode in {10008, 10009}
        return {
            "ok": ok,
            "retcode": retcode,
            "comment": getattr(result, "comment", ""),
            "order": int(getattr(result, "order", 0) or 0),
            "deal": int(getattr(result, "deal", 0) or 0),
            "price": float(getattr(result, "price", 0) or 0),
            "volume": volume,
            "kind": order.kind,
            "entry": price,
            "leg": order.leg,
        }

    def modify_sl(self, ticket: int, sl: float, tp: float, settings: Settings) -> dict[str, Any]:
        if mt5 is None or not self._connected:
            raise RuntimeError("MT5 no está conectado")
        meta = self.symbol_meta(settings.symbol)
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": settings.symbol,
            "position": ticket,
            "sl": _round_price(sl, meta["digits"]),
            "tp": _round_price(tp, meta["digits"]) if tp else 0.0,
            "magic": settings.magic,
        }
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"modify falló: {mt5.last_error()}")
        return {"ok": int(result.retcode) in {10008, 10009}, "retcode": int(result.retcode)}


def _credentials_for_mode(mode: str) -> tuple[int | None, str, str]:
    prefix = "MT5_LIVE" if mode == "real" else "MT5_DEMO"
    login_raw = os.getenv(f"{prefix}_LOGIN") or os.getenv("MT5_LOGIN") or ""
    password = os.getenv(f"{prefix}_PASSWORD") or os.getenv("MT5_PASSWORD") or ""
    server = os.getenv(f"{prefix}_SERVER") or os.getenv("MT5_SERVER") or ""
    login = int(login_raw) if login_raw.strip().isdigit() else None
    return login, password, server


def _round_price(price: float, digits: int) -> float:
    return round(float(price), digits)


def _normalize_volume(volume: float, meta: dict[str, Any]) -> float:
    step = float(meta.get("volume_step") or 0.01)
    minimum = float(meta.get("volume_min") or 0.01)
    steps = round(volume / step)
    normalized = max(minimum, steps * step)
    return float(round(normalized, 8))


def _filling_type(filling_mode: int) -> int:
    if mt5 is None:
        return 1
    if filling_mode & 2:
        return mt5.ORDER_FILLING_IOC
    if filling_mode & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def _pending_kind(order_type: int) -> str:
    return {
        2: "BUY_LIMIT",
        3: "SELL_LIMIT",
        4: "BUY_STOP",
        5: "SELL_STOP",
    }.get(order_type, str(order_type))


def _build_request(
    order: PlannedOrder,
    settings: Settings,
    price: float,
    sl: float,
    tp: float,
    volume: float,
    comment: str,
    filling: int,
) -> dict[str, Any]:
    assert mt5 is not None
    if order.kind == "MARKET":
        action = mt5.TRADE_ACTION_DEAL
        order_type = mt5.ORDER_TYPE_BUY if order.side == "BUY" else mt5.ORDER_TYPE_SELL
    else:
        action = mt5.TRADE_ACTION_PENDING
        order_type = {
            "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
            "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
            "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
            "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
        }[order.kind]
    return {
        "action": action,
        "symbol": settings.symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": int(settings.deviation_points),
        "magic": int(settings.magic),
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }
