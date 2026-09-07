from src.models import Signal
from src.runtime import BotRuntime


def test_panel_cannot_execute_in_real(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "operating_mode: real\nlive_confirmed: true\ndry_run: false\nlot_size: 0.01\n",
        encoding="utf-8",
    )
    runtime = BotRuntime(tmp_path)
    runtime.config.set_mode("real", live_confirmed=True)
    signal = Signal(
        direction="BUY",
        symbol="XAUUSD",
        first_entry=4411,
        second_entry=4407,
        tp1=4415,
        tp2=4420,
        tp3=4430,
        sl=4403,
        raw_text="x",
        message_id="1",
    )
    report = runtime.execute_signal(signal, source="panel")
    assert report.rejected
    assert "Telegram" in report.rejected
