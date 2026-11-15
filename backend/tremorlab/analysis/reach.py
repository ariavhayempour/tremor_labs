"""Reach descent smoothness and end wobble from ToF distance (mm)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter

from tremorlab.analysis.errors import AnalysisError
from tremorlab.analysis.sampling import effective_fs

START_DROP_MM = 20.0
END_MM = 40.0
STALL_S = 0.5
SG_WINDOW_S = 0.3
SG_POLYORDER = 2
FINAL_ZONE_MM = 50.0

TOF_MAX_MM = 1300.0
DECREASE_EPS_MM = 2.0
SG_MIN_WINDOW = 5
MIN_ZONE_SAMPLES = 2

Arr = NDArray[np.float64]


@dataclass(frozen=True)
class ReachAttempt:
    """t s, mm raw, smoothed mm, residual mm; smoothness_mm residual RMS; wobble_ratio unitless."""

    t: NDArray[np.float64]
    mm: NDArray[np.float64]
    smoothed: NDArray[np.float64]
    residual: NDArray[np.float64]
    smoothness_mm: float
    wobble_ratio: float


@dataclass(frozen=True)
class ReachResult:
    """Means over valid attempts: smoothness_mm (mm), wobble_ratio (unitless)."""

    smoothness_mm: float
    wobble_ratio: float
    attempts: list[ReachAttempt]


def _clean(t: Arr, mm: Arr) -> tuple[Arr, Arr]:
    """Drop out-of-view readings (NaN, ≤ 0, > TOF_MAX_MM) and stale repeats of the previous mm."""
    t = np.asarray(t, dtype=np.float64)
    mm = np.asarray(mm, dtype=np.float64)
    keep = np.isfinite(t) & np.isfinite(mm) & (mm > 0) & (mm <= TOF_MAX_MM)
    t, mm = t[keep], mm[keep]
    order = np.argsort(t, kind="stable")
    t, mm = t[order], mm[order]
    fresh = np.ones(mm.size, dtype=bool)
    fresh[1:] = mm[1:] != mm[:-1]
    return t[fresh], mm[fresh]


def _sg_window(fs: float) -> int:
    """Odd Savitzky-Golay window (samples) nearest SG_WINDOW_S·fs, at least SG_MIN_WINDOW."""
    n = 2 * math.floor((SG_WINDOW_S * fs - 1) / 2 + 0.5) + 1
    return max(n, SG_MIN_WINDOW)


def _detect(t: Arr, mm: Arr) -> tuple[int, int] | None:
    """Inclusive descent bounds in an already cleaned series, or None."""
    if mm.size < SG_MIN_WINDOW:
        return None
    below = np.flatnonzero(mm < np.maximum.accumulate(mm) - START_DROP_MM)
    if below.size == 0:
        return None
    start = int(below[0])
    end = mm.size - 1
    low_i, low = start, float(mm[start])
    for i in range(start, mm.size):
        if mm[i] < END_MM:
            end = i
            break
        if mm[i] < low - DECREASE_EPS_MM:
            low_i, low = i, float(mm[i])
        elif t[i] - t[low_i] >= STALL_S:
            end = low_i
            break
    if end - start + 1 < SG_MIN_WINDOW:
        return None
    return start, end


def detect_descent(t: NDArray[np.float64], mm: NDArray[np.float64]) -> tuple[int, int] | None:
    """(start, end) indices of the descent after NaNs are removed, or None."""
    return _detect(*_clean(t, mm))


def _rms(x: Arr) -> float:
    return math.sqrt(float(np.mean(x * x)))


def _attempt(t: Arr, mm: Arr) -> ReachAttempt | None:
    """Smooth one cleaned window's descent on a uniform grid; None without a usable descent."""
    bounds = _detect(t, mm)
    if bounds is None:
        return None
    s, e = bounds
    t, mm = t[s : e + 1], mm[s : e + 1]
    fs = effective_fs(t)
    rel = t - t[0]
    n_grid = round(rel[-1] * fs) + 1
    grid = np.linspace(0.0, rel[-1], n_grid)
    window = min(_sg_window(fs), n_grid if n_grid % 2 else n_grid - 1)
    if window < SG_MIN_WINDOW:
        return None
    # Smooth on a uniform grid (SG assumes even spacing), then read it back at the real timestamps.
    smooth_grid = savgol_filter(np.interp(grid, rel, mm), window, SG_POLYORDER)
    smoothed = np.interp(rel, grid, smooth_grid)
    residual = mm - smoothed
    final = smoothed <= float(np.min(smoothed)) + FINAL_ZONE_MM
    if final.sum() < MIN_ZONE_SAMPLES or (~final).sum() < MIN_ZONE_SAMPLES:
        return None
    before = _rms(residual[~final])
    if before <= 0:
        return None
    return ReachAttempt(
        t=t,
        mm=mm,
        smoothed=smoothed,
        residual=residual,
        smoothness_mm=_rms(residual),
        wobble_ratio=_rms(residual[final]) / before,
    )


def analyze_reach(
    t: NDArray[np.float64], mm: NDArray[np.float64], marks: Sequence[float]
) -> ReachResult:
    """Windows split at marks (epoch s); AnalysisError("no_descent_detected") if none descend."""
    t, mm = _clean(t, mm)
    edges = np.sort(np.asarray(marks, dtype=np.float64))
    window_id = np.searchsorted(edges, t, side="right")
    attempts = []
    for w in range(edges.size + 1):
        sel = window_id == w
        attempt = _attempt(t[sel], mm[sel])
        if attempt is not None:
            attempts.append(attempt)
    if not attempts:
        raise AnalysisError("no_descent_detected", "no reach descent found")
    return ReachResult(
        smoothness_mm=float(np.mean([a.smoothness_mm for a in attempts])),
        wobble_ratio=float(np.mean([a.wobble_ratio for a in attempts])),
        attempts=attempts,
    )
