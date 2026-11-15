"""Finger-tap metrics from MediaPipe landmarks 0, 4, 8, 9."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import find_peaks

from tremorlab.analysis.errors import AnalysisError

TAP_PROMINENCE = 0.15
EDGE_WINDOW_S = 3.0
MIN_TAPS = 3

MIN_HAND_SIZE = 1e-6
LANDMARK_COUNT = 4

Arr = NDArray[np.float64]


@dataclass(frozen=True)
class TapFrame:
    """t s; lm is ((x, y) for landmarks 0, 4, 8, 9) in normalized image units, None if no hand."""

    t: float
    lm: tuple[tuple[float, float], ...] | None


@dataclass(frozen=True)
class TapResult:
    """taps_per_sec /s; amplitude, decrement, rhythm_cv unitless; t s; signal ratio; peak_idx."""

    taps_per_sec: float
    amplitude: float
    decrement: float
    rhythm_cv: float
    t: NDArray[np.float64]
    signal: NDArray[np.float64]
    peak_idx: NDArray[np.int64]


def tap_signal(frames: Sequence[TapFrame]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Drops frames without a hand; returns (t s, |p4-p8| / |p0-p9|)."""
    rows = [(f.t, f.lm) for f in frames if f.lm is not None and len(f.lm) >= LANDMARK_COUNT]
    if not rows:
        return np.zeros(0), np.zeros(0)
    t = np.array([r[0] for r in rows], dtype=np.float64)
    p = np.array([r[1][:LANDMARK_COUNT] for r in rows], dtype=np.float64)
    hand = np.linalg.norm(p[:, 0] - p[:, 3], axis=1)
    gap = np.linalg.norm(p[:, 1] - p[:, 2], axis=1)
    keep = np.isfinite(t) & np.isfinite(gap) & np.isfinite(hand) & (hand > MIN_HAND_SIZE)
    t, signal = t[keep], gap[keep] / hand[keep]
    # Browser timestamps can arrive out of order or repeated; keep the first frame per time.
    t, first = np.unique(t, return_index=True)
    return t, signal[first]


def _refined_times(t: Arr, y: Arr, peaks: NDArray[np.int64]) -> Arr:
    """Peak times in s from a parabola through each peak and its neighbours (uneven spacing)."""
    out = t[peaks].copy()
    for i, k in enumerate(peaks):
        if k <= 0 or k >= t.size - 1:
            continue
        x = t[k - 1 : k + 2] - t[k]
        a, b, _ = np.polyfit(x, y[k - 1 : k + 2], 2)
        if a < 0:
            out[i] = t[k] + float(np.clip(-b / (2 * a), x[0], x[2]))
    return out


def analyze_taps(frames: Sequence[TapFrame]) -> TapResult:
    """Raises AnalysisError("no_taps_detected") with fewer than MIN_TAPS peaks."""
    t, signal = tap_signal(frames)
    peaks = np.asarray(find_peaks(signal, prominence=TAP_PROMINENCE)[0], dtype=np.int64)
    if peaks.size < MIN_TAPS:
        raise AnalysisError("no_taps_detected", f"{peaks.size} taps found")
    starts = np.concatenate(([0], peaks[:-1]))
    pairs = zip(starts, peaks, strict=True)
    amps = np.array([signal[k] - np.min(signal[s : k + 1]) for s, k in pairs])
    tp = _refined_times(t, signal, peaks)
    span = float(tp[-1] - tp[0])
    if span <= 0:
        raise AnalysisError("no_taps_detected", "taps share one timestamp")
    first = float(np.mean(amps[tp <= tp[0] + EDGE_WINDOW_S]))
    last = float(np.mean(amps[tp >= tp[-1] - EDGE_WINDOW_S]))
    intervals = np.diff(tp)
    return TapResult(
        taps_per_sec=(peaks.size - 1) / span,
        amplitude=float(np.mean(amps)),
        decrement=(last - first) / first if first > 0 else 0.0,
        rhythm_cv=float(np.std(intervals) / np.mean(intervals)),
        t=t,
        signal=signal,
        peak_idx=peaks,
    )
