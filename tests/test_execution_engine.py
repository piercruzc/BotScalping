from src.config import Settings
from src.execution_engine import ExecutionEngine, choose_best_entry
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


def _sell_piply() -> Signal:
    return Signal(
        direction="SELL",
        symbol="XAUUSD",
        first_entry=4384,
        second_entry=4388,
        tp1=4380,
        tp2=4375,
        tp3=4365,
        sl=4392,
        raw_text="",
    )


def test_same_lot_and_same_entry_three_tps():
    settings = Settings(lot_size=0.02, entry_tolerance=0.2)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.8, ask=4411.0), settings)
    assert plan.rejected is None
    assert [order.volume for order in plan.accepted_orders] == [0.02, 0.02, 0.02]
    assert [order.entry for order in plan.accepted_orders] == [4411, 4411, 4411]
    assert [order.tp for order in plan.accepted_orders] == [4415, 4420, 4430]
    assert [order.sl for order in plan.accepted_orders] == [4403, 4403, 4403]


def test_sell_near_first_uses_first_with_tp1_tp2_tp3():
    settings = Settings(entry_tolerance=0.2, near_entry_pips=20)
    plan = ExecutionEngine().plan(_sell_piply(), Tick(bid=4384.1, ask=4384.3), settings)
    assert [order.entry for order in plan.accepted_orders] == [4384, 4384, 4384]
    assert [order.tp for order in plan.accepted_orders] == [4380, 4375, 4365]
    assert [order.sl for order in plan.accepted_orders] == [4392, 4392, 4392]


def test_sell_near_second_uses_second():
    settings = Settings(near_entry_pips=20)
    entry = choose_best_entry(_sell_piply(), Tick(bid=4388.0, ask=4388.2), settings)
    assert entry == 4388


def test_sell_between_picks_higher_entry():
    settings = Settings(near_entry_pips=5)
    entry = choose_best_entry(_sell_piply(), Tick(bid=4386.0, ask=4386.2), settings)
    assert entry == 4388


def test_buy_between_picks_lower_entry():
    settings = Settings(near_entry_pips=5)
    entry = choose_best_entry(_buy(), Tick(bid=4408.8, ask=4409.0), settings)
    assert entry == 4407


def test_buy_limit_when_ask_above_chosen_entry():
    settings = Settings(entry_tolerance=0.05, near_entry_pips=20)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4412.8, ask=4413.0), settings)
    assert {order.kind for order in plan.accepted_orders} == {"BUY_LIMIT"}
    assert {order.entry for order in plan.accepted_orders} == {4411}


def test_market_inside_tolerance():
    settings = Settings(entry_tolerance=0.2, near_entry_pips=20)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410.9, ask=4411.05), settings)
    assert {order.kind for order in plan.accepted_orders} == {"MARKET"}


def test_reject_when_past_tp1():
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4416, ask=4416.2), Settings())
    assert plan.rejected and "TP1" in plan.rejected


def test_still_places_when_far_from_entries_if_tp1_not_hit():
    settings = Settings(near_entry_pips=5, pip_size=0.1)
    plan = ExecutionEngine().plan(_sell_piply(), Tick(bid=4405, ask=4405.2), settings)
    assert plan.rejected is None
    assert [order.entry for order in plan.accepted_orders] == [4388, 4388, 4388]
    assert {order.kind for order in plan.accepted_orders} == {"SELL_STOP"}


def test_places_sell_limit_if_below_entry_but_above_tp1():
    settings = Settings(near_entry_pips=5)
    plan = ExecutionEngine().plan(_sell_piply(), Tick(bid=4382, ask=4382.2), settings)
    assert plan.rejected is None
    assert [order.entry for order in plan.accepted_orders] == [4384, 4384, 4384]
    assert {order.kind for order in plan.accepted_orders} == {"SELL_LIMIT"}


def test_wide_spread_rejected():
    settings = Settings(max_spread_pips=10, pip_size=0.1)
    plan = ExecutionEngine().plan(_buy(), Tick(bid=4410, ask=4413), settings)
    assert plan.rejected and "Spread" in plan.rejected
