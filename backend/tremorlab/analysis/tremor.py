"""Rest/posture tremor: high-pass, Welch PSD, 3-12 Hz peak, band RMS, detection and score."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

HP_CUTOFF_HZ = 2.0
BAND_HZ = (3.0, 12.0)
WELCH_WINDOW_S = 4.0
PEAK_TO_MEDIAN_MIN = 6.0
RMS_MIN_MS2 = 0.02
SCORE_FLOOR_MS2 = 0.005
SCORE_CEIL_MS2 = 2.0
MIN_SECONDS = 4.0


@dataclass(frozen=True)
class TremorResult:
    """peak_hz Hz (None if no tremor detected); strength_ms2 m/s² band RMS; score 0-100;
    freqs Hz; psd (m/s²)²/Hz summed over axes; valid_seconds s analyzed."""

    peak_hz: float | None
    strength_ms2: float
    strength_score: float
    tremor_detected: bool
    freqs: NDArray[np.float64]
    psd: NDArray[np.float64]
    valid_seconds: float


def strength_to_score(rms_ms2: float) -> float:
    """clamp(100·log10(rms/0.005)/log10(2.0/0.005), 0, 100) for rms in m/s²."""
    raise NotImplementedError


def tremor_spectrum(
    t: NDArray[np.float64], acc: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """t (N,) s, acc (N, 3) m/s² → (freqs Hz, summed PSD (m/s²)²/Hz, fs Hz)."""
    raise NotImplementedError


def analyze_tremor(
    t: NDArray[np.float64], acc: NDArray[np.float64], *, trim: bool = True
) -> TremorResult:
    """t (N,) s, acc (N, 3) m/s²; insufficient_valid_data under MIN_SECONDS of data."""
    raise NotImplementedError
