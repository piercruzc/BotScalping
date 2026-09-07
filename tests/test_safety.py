import pytest

from src.config import Settings
from src.models import AccountSnapshot
from src.safety import Safety, SafetyError


def _account(is_demo: bool, connected: bool = True) -> AccountSnapshot:
    return AccountSnapshot(
        connected=connected,
        is_demo=is_demo,
        trade_mode="demo" if is_demo else "real",
    )


def test_demo_ok_on_demo_account():
    Safety().assert_can_trade(
        Settings(operating_mode="demo", dry_run=False),
        _account(True),
        "panel",
    )


def test_blocks_panel_orders_in_real():
    with pytest.raises(SafetyError, match="Telegram"):
        Safety().assert_can_trade(
            Settings(operating_mode="real", live_confirmed=True, dry_run=False),
            _account(False),
            "panel",
        )


def test_telegram_ok_in_real_when_confirmed():
    Safety().assert_can_trade(
        Settings(operating_mode="real", live_confirmed=True, dry_run=False),
        _account(False),
        "telegram",
    )


def test_real_without_confirm():
    with pytest.raises(SafetyError, match="confirmado"):
        Safety().assert_can_trade(
            Settings(operating_mode="real", live_confirmed=False, dry_run=False),
            _account(False),
            "telegram",
        )


def test_mode_mismatch():
    with pytest.raises(SafetyError, match="REAL"):
        Safety().assert_can_trade(
            Settings(operating_mode="demo", dry_run=False),
            _account(False),
            "telegram",
        )


def test_dry_run_blocks_send():
    with pytest.raises(SafetyError, match="Dry-run"):
        Safety().assert_can_trade(
            Settings(operating_mode="demo", dry_run=True),
            _account(True),
            "panel",
        )
