"""Comparison of a metric against the user's own history."""

import math
from collections.abc import Sequence

BASELINE_MIN_N = 3


def compare(value: float, history: Sequence[float], min_n: int = BASELINE_MIN_N) -> float | None:
    """Percent difference of value from the history mean, or None with fewer than min_n entries."""
    finite = [h for h in history if math.isfinite(h)]
    if len(finite) < min_n or not finite or not math.isfinite(value):
        return None
    mean = sum(finite) / len(finite)
    if mean == 0:
        return None
    return 100.0 * (value - mean) / abs(mean)
