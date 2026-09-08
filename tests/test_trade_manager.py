from types import SimpleNamespace

from src.config import Settings
from src.logs import LogBuffer
from src.models import AccountSnapshot, PositionSnapshot, Tick
from src.state import ActiveSignalState
from src.trade_manager import (
    TradeManager,
    clamp_protective_sl,
    sl_break_even,
    sl_lock_tp1,
    trail_stop,
)


def test_lock_after_tp2_buy_sits_at_tp1():
    assert sl_lock_tp1("BUY", 4380, 0.2) == 4379.8


def test_lock_after_tp2_sell_sits_at_tp1():
    assert sl_lock_tp1("SELL", 4380, 0.2) == 4380.2


def test_be_buy_locks_small_profit():
    assert sl_break_even("BUY", 4384, 0.8) == 4384.8


def test_be_sell_locks_small_profit():
    assert sl_break_even("SELL", 4388, 0.8) == 4387.2


def test_trail_percent_buy_never_below_tp1_floor():
    tick = Tick(bid=4400, ask=4400.2)
    sl = trail_stop("BUY", entry=4384, market=tick, trail_percent=50, trail_distance=4, floor=4379.8)
    # 50% of 16 profit = 8 → 4384+8=4392, above floor
    assert sl == 4392.0


def test_trail_percent_sell_can_lock_beyond_tp1():
    tick = Tick(bid=4360, ask=4360.2)
    sl = trail_stop("SELL", entry=4388, market=tick, trail_percent=50, trail_distance=4, floor=4380.2)
    assert sl == 4374.1


def test_trail_sell_does_not_loosen_above_tp1_lock():
    tick = Tick(bid=4382, ask=4382.2)
    sl = trail_stop("SELL", entry=4388, market=tick, trail_percent=10, trail_distance=4, floor=4380.2)
    # 10% of 5.8 = 0.58 → 4388-0.58=4387.42, peor que el lock 4380.2 → se queda en el piso
    assert sl == 4380.2


def test_clamp_buy_uses_price_if_be_is_too_close():
    tick = Tick(bid=4384.2, ask=4384.4)
    sl = clamp_protective_sl("BUY", 4384.8, tick, 0.05)
    assert sl == 4384.15


def test_clamp_sell_uses_price_if_be_is_too_close():
    tick = Tick(bid=4383.6, ask=4383.8)
    sl = clamp_protective_sl("SELL", 4383.2, tick, 0.05)
    assert sl == 4383.85


def test_after_tp1_moves_remaining_sl_to_be_plus():
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=True)
    TradeManager(runtime).tick()
    assert active.be_done is True
    assert [call["sl"] for call in mt5.modifies] == [4384.8, 4384.8]


def test_after_tp1_retries_if_modify_fails():
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=False)
    TradeManager(runtime).tick()
    assert active.be_done is False
    assert mt5.modifies


def test_after_tp1_matches_by_tp_if_comment_stripped():
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=True, comments=("", ""), tickets=[])
    TradeManager(runtime).tick()
    assert active.be_done is True
    assert len(mt5.modifies) == 2


def test_after_tp1_still_moves_if_price_retraces():
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=True, bid=4385)
    TradeManager(runtime).tick()
    assert active.be_done is True
    assert [call["sl"] for call in mt5.modifies] == [4384.8, 4384.8]


def test_retries_be_if_state_marked_done_but_sl_still_original():
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=True)
    active.be_done = True
    TradeManager(runtime).tick()
    assert [call["sl"] for call in mt5.modifies] == [4384.8, 4384.8]
    runtime, active, mt5 = _runtime_after_tp1(modify_ok=True, still_has_tp1=True, bid=4385)
    TradeManager(runtime).tick()
    assert active.be_done is False
    assert mt5.modifies == []


def _runtime_after_tp1(
    *,
    modify_ok: bool,
    comments: tuple[str, ...] = ("p|abc12345|2", "p|abc12345|3"),
    tickets: list[int] | None = None,
    still_has_tp1: bool = False,
    bid: float = 4388.2,
):
    settings = Settings(dry_run=False, be_profit_pips=8.0, pip_size=0.1)
    active = ActiveSignalState(
        message_id="abc12345",
        direction="BUY",
        tp1=4388,
        tp2=4392,
        tp3=4400,
        sl=4376,
        token="abc12345",
        tickets=tickets if tickets is not None else [101, 102, 103],
        entry=4384,
        source="telegram",
    )
    positions = []
    if still_has_tp1:
        positions.append(
            PositionSnapshot(
                ticket=101,
                symbol="XAUUSD",
                side="BUY",
                volume=0.01,
                price_open=4384,
                sl=4376,
                tp=4388,
                profit=1.0,
                comment="p|abc12345|1",
                magic=settings.magic,
            )
        )
    positions.extend(
        [
            PositionSnapshot(
                ticket=102,
                symbol="XAUUSD",
                side="BUY",
                volume=0.01,
                price_open=4384,
                sl=4376,
                tp=4392,
                profit=4.0,
                comment=comments[0] if comments else "",
                magic=settings.magic,
            ),
            PositionSnapshot(
                ticket=103,
                symbol="XAUUSD",
                side="BUY",
                volume=0.01,
                price_open=4384,
                sl=4376,
                tp=4400,
                profit=4.0,
                comment=comments[1] if len(comments) > 1 else "",
                magic=settings.magic,
            ),
        ]
    )
    mt5 = _FakeMT5(settings, positions, modify_ok=modify_ok, bid=bid)
    state = SimpleNamespace(
        list_actives=lambda: [active],
        remove_active=lambda _mid: None,
        update_active=lambda _item: None,
    )
    runtime = SimpleNamespace(
        config=SimpleNamespace(get=lambda: settings),
        mt5=mt5,
        logs=LogBuffer(),
        state=state,
    )
    return runtime, active, mt5


class _FakeMT5:
    def __init__(
        self,
        settings: Settings,
        positions: list[PositionSnapshot],
        modify_ok: bool,
        bid: float = 4388.2,
    ) -> None:
        self.settings = settings
        self._positions = positions
        self.modify_ok = modify_ok
        self.bid = bid
        self.modifies: list[dict] = []

    def account(self) -> AccountSnapshot:
        return AccountSnapshot(connected=True, is_demo=True, trade_mode="demo")

    def tick(self, _symbol: str) -> Tick:
        return Tick(bid=self.bid, ask=self.bid + 0.2)

    def positions(self, _symbol: str, _magic: int) -> list[PositionSnapshot]:
        return list(self._positions)

    def pendings(self, _symbol: str, _magic: int) -> list:
        return []

    def stop_distance(self, _symbol: str) -> float:
        return 0.02

    def closed_by_tp(self, *_args, **_kwargs) -> bool:
        return False

    def modify_sl(self, ticket: int, sl: float, tp: float, _settings: Settings) -> dict:
        self.modifies.append({"ticket": ticket, "sl": sl, "tp": tp})
        return {"ok": self.modify_ok, "retcode": 10009 if self.modify_ok else 10016, "hint": ""}
