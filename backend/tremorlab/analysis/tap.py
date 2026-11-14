"""Finger-tap metrics from MediaPipe landmarks 0, 4, 8, 9."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

TAP_PROMINENCE = 0.15
EDGE_WINDOW_S = 3.0
MIN_TAPS = 3


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
    raise NotImplementedError


def analyze_taps(frames: Sequence[TapFrame]) -> TapResult:
    """Raises AnalysisError("no_taps_detected") with fewer than MIN_TAPS peaks."""
    raise NotImplementedError
