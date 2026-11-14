"""Sample-rate and timing helpers. Times in seconds, rates in Hz."""

import numpy as np
from numpy.typing import NDArray

TRIM_SECONDS = 2.0
RESAMPLE_CV_LIMIT = 0.05


def effective_fs(t: NDArray[np.float64]) -> float:
    """Median of 1/diff(t) in Hz; raises AnalysisError("insufficient_valid_data") if len(t) < 2."""
    raise NotImplementedError


def trim_edges(
    t: NDArray[np.float64], x: NDArray[np.float64], seconds: float = TRIM_SECONDS
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Drop the first and last `seconds` s of (t, x); x is indexed along axis 0."""
    raise NotImplementedError


def needs_resample(t: NDArray[np.float64], cv_limit: float = RESAMPLE_CV_LIMIT) -> bool:
    """True when the coefficient of variation of diff(t) exceeds cv_limit."""
    raise NotImplementedError


def resample_uniform(
    t: NDArray[np.float64], x: NDArray[np.float64], fs: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Linear interpolation of x (axis 0) onto a uniform grid at fs Hz from t[0]."""
    raise NotImplementedError


def max_gap(t: NDArray[np.float64]) -> float:
    """Largest diff(t) in seconds (0.0 for fewer than 2 samples)."""
    raise NotImplementedError
