import pytest

from btc_engine.core.sequence import SequenceGap, SequenceTracker


def test_sequence_tracker_detects_gap() -> None:
    tracker = SequenceTracker()
    tracker.observe("book", 10)
    tracker.observe("book", 11)
    with pytest.raises(SequenceGap):
        tracker.observe("book", 13)


def test_sequence_tracker_ignores_duplicate() -> None:
    tracker = SequenceTracker()
    tracker.observe("book", 10)
    tracker.observe("book", 10)
    assert tracker.last["book"] == 10
