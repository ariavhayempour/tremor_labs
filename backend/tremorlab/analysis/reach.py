"""Reach descent smoothness and end wobble from ToF distance (mm)."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

START_DROP_MM = 20.0
END_MM = 40.0
STALL_S = 0.5
SG_WINDOW_S = 0.3
SG_POLYORDER = 2
FINAL_ZONE_MM = 50.0


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


def detect_descent(t: NDArray[np.float64], mm: NDArray[np.float64]) -> tuple[int, int] | None:
    """(start, end) indices of the descent after NaNs are removed, or None."""
    raise NotImplementedError


def analyze_reach(
    t: NDArray[np.float64], mm: NDArray[np.float64], marks: Sequence[float]
) -> ReachResult:
    """Windows split at marks (epoch s); AnalysisError("no_descent_detected") if none descend."""
    raise NotImplementedError
