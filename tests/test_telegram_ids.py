from src.telegram_ids import channel_candidates


def test_username_passthrough():
    assert channel_candidates("@piplyvip") == ["@piplyvip"]


def test_negative_channel_id_kept():
    assert channel_candidates("-1001234567890") == [-1001234567890]


def test_positive_id_also_tries_minus_100():
    assert channel_candidates("1234567890") == [1234567890, -1001234567890]
