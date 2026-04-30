"""Walk-forward and purged k-fold splitters for time-series CV.

PRD §4.4: walk-forward expanding train window, fixed test window of one
month, rolling forward; purged k-fold uses a 7-day buffer between train and
test to defeat temporal leakage.

Both yield (train_indices, test_indices) tuples — integer arrays compatible
with numpy/pandas slicing. No numpy dependency at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, Sequence


def _normalize_timestamps(timestamps: Sequence[datetime]) -> list[datetime]:
    ts = list(timestamps)
    for prev, curr in zip(ts, ts[1:]):
        if curr < prev:
            raise ValueError("timestamps must be non-decreasing")
    return ts


@dataclass
class WalkForwardSplitter:
    """Expanding train window, fixed test window, rolling forward.

    train_period: minimum length of the initial train window.
    test_period: length of each test fold.
    step: how far the test window advances each iteration (defaults to
      test_period for non-overlapping folds).

    `split(timestamps)` yields (train_idx, test_idx) where train ends at
    test_start (no purge) and test runs [test_start, test_start+test_period).
    """

    train_period: timedelta = timedelta(days=365)
    test_period: timedelta = timedelta(days=30)
    step: timedelta | None = None

    def split(self, timestamps: Sequence[datetime]) -> Iterator[tuple[list[int], list[int]]]:
        if not timestamps:
            return
        ts = _normalize_timestamps(timestamps)
        step = self.step or self.test_period
        start = ts[0]
        end = ts[-1]
        test_start = start + self.train_period
        while test_start + self.test_period <= end + timedelta(microseconds=1):
            test_end = test_start + self.test_period
            train_idx = [i for i, t in enumerate(ts) if t < test_start]
            test_idx = [i for i, t in enumerate(ts) if test_start <= t < test_end]
            if train_idx and test_idx:
                yield train_idx, test_idx
            test_start = test_start + step


@dataclass
class PurgedKFold:
    """K-fold with a purge gap between train and test to prevent temporal
    leakage.

    n_splits: number of folds.
    purge: timedelta gap. Train rows whose timestamps fall within
      [test_start - purge, test_end + purge] are excluded.

    Yields (train_idx, test_idx).
    """

    n_splits: int = 5
    purge: timedelta = timedelta(days=7)

    def split(self, timestamps: Sequence[datetime]) -> Iterator[tuple[list[int], list[int]]]:
        if self.n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        ts = _normalize_timestamps(timestamps)
        n = len(ts)
        if n < self.n_splits:
            return
        fold_size = n // self.n_splits
        for k in range(self.n_splits):
            test_start_idx = k * fold_size
            test_end_idx = (k + 1) * fold_size if k < self.n_splits - 1 else n
            test_idx = list(range(test_start_idx, test_end_idx))
            test_start_time = ts[test_start_idx]
            test_end_time = ts[test_end_idx - 1]
            purge_lo = test_start_time - self.purge
            purge_hi = test_end_time + self.purge
            train_idx = [
                i for i, t in enumerate(ts)
                if i not in range(test_start_idx, test_end_idx)
                and not (purge_lo <= t <= purge_hi)
            ]
            if train_idx and test_idx:
                yield train_idx, test_idx
