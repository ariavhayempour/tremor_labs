"""Sample-rate and timing helpers. Times in seconds, rates in Hz."""

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.errors import AnalysisError

TRIM_SECONDS = 2.0
RESAMPLE_CV_LIMIT = 0.05
GRID_EPS = 1e-9


def effective_fs(t: NDArray[np.float64]) -> float:
    """Median of 1/diff(t) in Hz; raises AnalysisError("insufficient_valid_data") if len(t) < 2."""
    if t.size < 2:
        raise AnalysisError("insufficient_valid_data", "need at least 2 samples for a rate")
    dt = np.diff(t)
    dt = dt[dt > 0]
    if dt.size == 0:
        raise AnalysisError("insufficient_valid_data", "timestamps do not advance")
    return float(np.median(1.0 / dt))


def trim_edges(
    t: NDArray[np.float64], x: NDArray[np.float64], seconds: float = TRIM_SECONDS
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Drop the first and last `seconds` s of (t, x); x is indexed along axis 0."""
    if t.size == 0:
        return t, x
    keep = (t >= t[0] + seconds) & (t <= t[-1] - seconds)
    return t[keep], x[keep]


def needs_resample(t: NDArray[np.float64], cv_limit: float = RESAMPLE_CV_LIMIT) -> bool:
    """True when the coefficient of variation of diff(t) exceeds cv_limit."""
    if t.size < 3:
        return False
    dt = np.diff(t)
    mean = float(np.mean(dt))
    if mean <= 0:
        return True
    return float(np.std(dt)) / mean > cv_limit


def resample_uniform(
    t: NDArray[np.float64], x: NDArray[np.float64], fs: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Linear interpolation of x (axis 0) onto a uniform grid at fs Hz from t[0]."""
    if t.size == 0:
        return t, x
    n = int(np.floor((t[-1] - t[0]) * fs + GRID_EPS)) + 1
    rel = np.arange(n, dtype=np.float64) / fs
    # Interpolate on times relative to t[0] to keep precision with epoch-second timestamps.
    trel = t - t[0]
    if x.ndim == 1:
        return t[0] + rel, np.interp(rel, trel, x)
    cols = [np.interp(rel, trel, x[:, i]) for i in range(x.shape[1])]
    return t[0] + rel, np.column_stack(cols)


def max_gap(t: NDArray[np.float64]) -> float:
    """Largest diff(t) in seconds (0.0 for fewer than 2 samples)."""
    if t.size < 2:
        return 0.0
    return float(np.max(np.diff(t)))
