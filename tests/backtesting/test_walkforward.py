"""Walk-forward + purged k-fold splitter behavior."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sigil.backtesting.walkforward import PurgedKFold, WalkForwardSplitter


def _daily_timestamps(n: int, start: datetime | None = None) -> list[datetime]:
    start = start or datetime(2025, 1, 1)
    return [start + timedelta(days=i) for i in range(n)]


def test_walkforward_yields_non_overlapping_test_folds():
    ts = _daily_timestamps(400)
    splitter = WalkForwardSplitter(
        train_period=timedelta(days=180),
        test_period=timedelta(days=30),
    )
    folds = list(splitter.split(ts))
    assert len(folds) >= 2
    seen_test_indices: set[int] = set()
    prev_train_size = 0
    for train_idx, test_idx in folds:
        for i in test_idx:
            assert i not in seen_test_indices
            seen_test_indices.add(i)
        assert train_idx
        assert test_idx
        # train end strictly precedes test start
        assert max(train_idx) < min(test_idx)
        # expanding window grows monotonically
        assert len(train_idx) >= prev_train_size
        prev_train_size = len(train_idx)


def test_walkforward_no_folds_when_too_short():
    ts = _daily_timestamps(60)
    splitter = WalkForwardSplitter(
        train_period=timedelta(days=180),
        test_period=timedelta(days=30),
    )
    assert list(splitter.split(ts)) == []


def test_walkforward_handles_empty_timestamps():
    splitter = WalkForwardSplitter()
    assert list(splitter.split([])) == []


def test_purged_kfold_respects_purge_gap():
    ts = _daily_timestamps(100)
    splitter = PurgedKFold(n_splits=5, purge=timedelta(days=7))
    folds = list(splitter.split(ts))
    assert len(folds) == 5
    for train_idx, test_idx in folds:
        test_times = [ts[i] for i in test_idx]
        train_times = [ts[i] for i in train_idx]
        test_lo, test_hi = min(test_times), max(test_times)
        for tt in train_times:
            # purge zone: within 7 days of test window end on either side
            assert not (test_lo - timedelta(days=7) <= tt <= test_hi + timedelta(days=7))


def test_purged_kfold_train_test_disjoint():
    ts = _daily_timestamps(100)
    splitter = PurgedKFold(n_splits=4, purge=timedelta(days=3))
    for train_idx, test_idx in splitter.split(ts):
        assert set(train_idx).isdisjoint(set(test_idx))
        assert train_idx
        assert test_idx


def test_purged_kfold_rejects_n_splits_below_two():
    with pytest.raises(ValueError):
        list(PurgedKFold(n_splits=1).split(_daily_timestamps(10)))


def test_walkforward_rejects_unsorted_timestamps():
    ts = _daily_timestamps(10)
    ts[3], ts[5] = ts[5], ts[3]
    with pytest.raises(ValueError):
        list(WalkForwardSplitter().split(ts))
