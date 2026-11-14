"""Comparison of a metric against the user's own history."""

from collections.abc import Sequence

BASELINE_MIN_N = 3


def compare(value: float, history: Sequence[float], min_n: int = BASELINE_MIN_N) -> float | None:
    """Percent difference of value from the history mean, or None with fewer than min_n entries."""
    raise NotImplementedError
