from src.config import Settings
from src.execution_engine import ExecutionEngine
from src.models import Signal, Tick


def _buy(**kwargs) -> Signal:
    data = dict(
        direction="BUY",
        symbol="XAUUSD",
        first_entry=4411,
        second_entry=4407,
        tp1=4415,
        tp2=4420,
        tp3=4430,
        sl=4403,
        raw_text="",
    )
    data.update(kwargs)
    return Signal(**data)


def _sell() -> Signal:
    return Signal(
        direction="SELL",
        symbol="XAUUSD",
        first_entry=4389,
        second_entry=4393,
        tp1=4385,
        tp2=4378,
        tp3=4370,
        sl=4397,
        raw_text="",
    )


def test_same_lot_on_three_legs():
    settings = Settings(lot_size=0.02, trail_enabled=False)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.8, ask=4411.0), settings)
    assert plan.rejected is None
    assert [order.volume for order in plan.accepted_orders] == [0.02, 0.02, 0.02]


def test_buy_limit_when_ask_above_entry():
    settings = Settings(entry_tolerance=0.05, trail_enabled=False)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4412.8, ask=4413.0), settings)
    kinds = [order.kind for order in plan.accepted_orders]
    assert kinds == ["BUY_LIMIT", "BUY_LIMIT", "BUY_LIMIT"]


def test_buy_stop_when_ask_below_zone():
    settings = Settings(entry_tolerance=0.05, trail_enabled=False, chase_buffer_pips=15)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4405.8, ask=4406.0), settings)
    kinds = [order.kind for order in plan.accepted_orders]
    assert kinds == ["BUY_STOP", "BUY_STOP", "MARKET"] or "BUY_STOP" in kinds


def test_market_inside_tolerance():
    settings = Settings(entry_tolerance=0.2, trail_enabled=False)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.9, ask=4411.05), settings)
    assert plan.orders[0].kind == "MARKET"


def test_reject_when_past_tp1():
    settings = Settings()
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4416, ask=4416.2), settings)
    assert plan.rejected and "TP1" in plan.rejected


def test_sell_limit_when_bid_below_entry():
    settings = Settings(entry_tolerance=0.05, trail_enabled=False)
    plan = ExecutionEngine().plan(_sell(), Tick(bid=4387, ask=4387.2), settings)
    assert plan.orders[0].kind == "SELL_LIMIT"


def test_all_legs_use_tp3_by_default():
    settings = Settings(trail_enabled=True, split_take_profits=False)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.8, ask=4411.0), settings)
    assert [order.tp for order in plan.accepted_orders] == [4430, 4430, 4430]


def test_split_assigns_tp1_tp2_tp3():
    settings = Settings(trail_enabled=True, split_take_profits=True)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.8, ask=4411.0), settings)
    assert [order.tp for order in plan.accepted_orders] == [4415, 4420, 4430]


def test_wide_spread_rejected():
    settings = Settings(max_spread_pips=10, pip_size=0.1)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410, ask=4413), settings)
    assert plan.rejected and "Spread" in plan.rejected
