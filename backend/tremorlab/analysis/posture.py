"""Posture tremor gated by hand height: only in-band ToF runs count."""

import numpy as np
from numpy.typing import NDArray

from tremorlab.analysis.tremor import TremorResult

BAND_HALF_WIDTH_MM = 30.0
MIN_RUN_S = 4.0
MIN_VALID_S = 20.0
TOF_VALID_RANGE_MM = (20.0, 1300.0)
TOF_MATCH_MAX_S = 0.2


def band_from_start(start_mm: float, half_width: float = BAND_HALF_WIDTH_MM) -> tuple[float, float]:
    """(start - half_width, start + half_width) in mm."""
    raise NotImplementedError


def in_band_mask(
    t_imu: NDArray[np.float64],
    t_tof: NDArray[np.float64],
    mm: NDArray[np.float64],
    band: tuple[float, float],
) -> NDArray[np.bool_]:
    """Per-IMU-sample in-band flag; invalid ToF dropped; IMU >0.2 s from valid ToF is out."""
    raise NotImplementedError


def analyze_posture(
    t_imu: NDArray[np.float64],
    acc: NDArray[np.float64],
    t_tof: NDArray[np.float64],
    mm: NDArray[np.float64],
    band: tuple[float, float],
) -> TremorResult:
    """Weighted PSD over in-band runs ≥ MIN_RUN_S; insufficient_valid_data under MIN_VALID_S."""
    raise NotImplementedError
