from src.state import (
    ActiveSignalState,
    StateStore,
    comment_belongs,
    entries_overlap,
    signal_token,
)


def test_legacy_single_active_loads_as_list(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        '{"processed_ids":["1"],"active":{"message_id":"99","direction":"SELL","tp1":4380,"sl":4392}}',
        encoding="utf-8",
    )
    store = StateStore(path)
    assert len(store.list_actives()) == 1
    assert store.list_actives()[0].token == "99"


def test_comment_belongs_isolates_signals():
    assert comment_belongs("p|abc12345|1", "abc12345")
    assert not comment_belongs("p|zzzzzzzz|1", "abc12345")


def test_same_direction_same_entry_overlaps():
    other = ActiveSignalState(message_id="1", direction="SELL", tp1=4380, sl=4392, entry=4384)
    assert entries_overlap("SELL", 4384, other, 0.2)
    assert not entries_overlap("BUY", 4384, other, 0.2)
    assert not entries_overlap("SELL", 4411, other, 0.2)


def test_token_from_message_id():
    assert signal_token("123456789") == "23456789"
