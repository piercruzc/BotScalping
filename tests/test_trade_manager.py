from src.models import Tick
from src.trade_manager import sl_break_even, sl_lock_tp1, trail_stop


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
